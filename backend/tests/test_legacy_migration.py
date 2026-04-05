import sqlite3
import pytest
from unittest.mock import patch

import chromadb

from src.memory.legacy_migration import migrate_legacy_collection
from src.memory.embedding_state import ensure_row, get_active_signature


@pytest.fixture
def test_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE embedding_state ("
        "id INTEGER PRIMARY KEY, active_signature TEXT, updated_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE resumes ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, version TEXT, "
        "file_path TEXT, file_type TEXT, extracted_text TEXT, "
        "last_index_signature TEXT, last_index_status TEXT, last_index_error TEXT, "
        "created_at TEXT DEFAULT (datetime('now')))"
    )
    conn.execute(
        "INSERT INTO resumes (id, name, file_path, file_type, extracted_text) "
        "VALUES (1, 'A.pdf', 'p', 'pdf', 'alpha')"
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture(autouse=True)
def mock_env(test_db, tmp_path, monkeypatch):
    vectordb = str(tmp_path / "vectordb")
    monkeypatch.setenv("VECTORDB_PATH", vectordb)
    monkeypatch.setenv("JOBTRACKER_DB_PATH", test_db)

    def make_conn():
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        return conn
    monkeypatch.setattr("src.memory.embedding_state.get_connection", make_conn)
    monkeypatch.setattr("src.memory.legacy_migration.get_connection", make_conn)
    ensure_row()
    yield vectordb


@pytest.fixture
def fake_config():
    with patch("src.memory.legacy_migration.load_model_config") as m:
        m.return_value = {
            "embedding": {"provider": "sentence_transformer", "model": "all-MiniLM-L6-v2"}
        }
        yield m


def test_migration_skips_when_active_signature_set(fake_config):
    from src.memory.embedding_state import set_active_signature
    set_active_signature("already_set")
    migrate_legacy_collection()
    assert get_active_signature() == "already_set"


def test_migration_skips_when_no_legacy_collection(fake_config):
    migrate_legacy_collection()
    assert get_active_signature() is None


def test_migration_copies_and_sets_signature(fake_config, mock_env):
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    client = chromadb.PersistentClient(path=mock_env)
    ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    legacy = client.get_or_create_collection(name="resume_chunks", embedding_function=ef)
    legacy.add(
        ids=["resume-1-chunk-0"],
        documents=["A.pdf -- general -- alpha text content here"],
        metadatas=[{"resume_id": 1, "resume_name": "A.pdf", "section_type": "general", "raw_text": "alpha text content here"}],
    )
    del legacy, client

    migrate_legacy_collection()

    assert get_active_signature() == "sentence_transformer__all_minilm_l6_v2"
    client2 = chromadb.PersistentClient(path=mock_env)
    names = [c.name for c in client2.list_collections()]
    assert "resume_chunks" not in names
    assert "resume_chunks__sentence_transformer__all_minilm_l6_v2" in names


def test_migration_marks_resumes_with_chunks_as_ok(fake_config, mock_env, test_db):
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    client = chromadb.PersistentClient(path=mock_env)
    ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    legacy = client.get_or_create_collection(name="resume_chunks", embedding_function=ef)
    legacy.add(
        ids=["resume-1-chunk-0"],
        documents=["alpha"],
        metadatas=[{"resume_id": 1, "resume_name": "A.pdf", "section_type": "general", "raw_text": "alpha"}],
    )
    del legacy, client

    migrate_legacy_collection()

    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT last_index_signature, last_index_status FROM resumes WHERE id=1").fetchone()
    conn.close()
    assert row["last_index_signature"] == "sentence_transformer__all_minilm_l6_v2"
    assert row["last_index_status"] == "ok"


def test_migration_idempotent_second_call(fake_config, mock_env):
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    client = chromadb.PersistentClient(path=mock_env)
    ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    client.get_or_create_collection(name="resume_chunks", embedding_function=ef)
    del client

    migrate_legacy_collection()
    first = get_active_signature()
    migrate_legacy_collection()
    assert get_active_signature() == first
