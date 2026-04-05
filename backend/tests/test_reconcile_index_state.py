"""Tests for reconcile_resume_index_state — startup heal that keeps SQL
per-resume state in sync with actual Chroma contents."""
import sqlite3
import pytest
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from src.memory.embedding_state import ensure_row, set_active_signature
from src.memory.rag import reconcile_resume_index_state


ACTIVE_SIG = "sentence_transformer__all_minilm_l6_v2"
ACTIVE_COLLECTION_NAME = f"resume_chunks__{ACTIVE_SIG}"


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
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture(autouse=True)
def wire_env(test_db, tmp_path, monkeypatch):
    vectordb = str(tmp_path / "vectordb")
    monkeypatch.setenv("VECTORDB_PATH", vectordb)

    def make_conn():
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        return conn
    monkeypatch.setattr("src.memory.embedding_state.get_connection", make_conn)
    monkeypatch.setattr("src.memory.rag.get_connection", make_conn)
    ensure_row()
    yield vectordb


def _insert_resume(db_path, rid, sig, status):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO resumes (id, name, file_path, file_type, extracted_text, "
        "last_index_signature, last_index_status) VALUES (?, 'r.pdf', 'p', 'pdf', 't', ?, ?)",
        (rid, sig, status),
    )
    conn.commit()
    conn.close()


def _row(db_path, rid):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    r = conn.execute(
        "SELECT last_index_signature, last_index_status FROM resumes WHERE id = ?",
        (rid,),
    ).fetchone()
    conn.close()
    return dict(r)


def _seed_active_collection(vectordb_path, resume_ids):
    client = chromadb.PersistentClient(path=vectordb_path)
    ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    col = client.get_or_create_collection(name=ACTIVE_COLLECTION_NAME, embedding_function=ef)
    for rid in resume_ids:
        col.add(
            ids=[f"resume-{rid}-chunk-0"],
            documents=[f"doc for {rid}"],
            metadatas=[{"resume_id": rid, "resume_name": "r.pdf", "section_type": "x", "raw_text": "t"}],
        )


def test_orphan_signature_gets_reset_to_null(test_db, wire_env):
    # No collections exist at all — any signature is orphaned
    set_active_signature(ACTIVE_SIG)
    _insert_resume(test_db, 1, "some_phantom_sig", "ok")
    reconcile_resume_index_state()
    row = _row(test_db, 1)
    assert row["last_index_signature"] is None
    assert row["last_index_status"] is None


def test_null_signature_healed_when_chunks_exist_in_active(test_db, wire_env):
    set_active_signature(ACTIVE_SIG)
    _seed_active_collection(wire_env, [5])
    _insert_resume(test_db, 5, None, None)
    reconcile_resume_index_state()
    row = _row(test_db, 5)
    assert row["last_index_signature"] == ACTIVE_SIG
    assert row["last_index_status"] == "ok"


def test_null_signature_stays_null_when_no_chunks(test_db, wire_env):
    set_active_signature(ACTIVE_SIG)
    _seed_active_collection(wire_env, [1])  # only resume 1 has chunks
    _insert_resume(test_db, 2, None, None)
    reconcile_resume_index_state()
    row = _row(test_db, 2)
    assert row["last_index_signature"] is None


def test_correct_signature_is_left_alone(test_db, wire_env):
    set_active_signature(ACTIVE_SIG)
    _seed_active_collection(wire_env, [3])
    _insert_resume(test_db, 3, ACTIVE_SIG, "ok")
    reconcile_resume_index_state()
    row = _row(test_db, 3)
    assert row["last_index_signature"] == ACTIVE_SIG
    assert row["last_index_status"] == "ok"


def test_noop_when_no_active_signature(test_db, wire_env):
    _insert_resume(test_db, 1, "any_sig", "ok")
    # active_signature is NULL; reconcile should still clear orphan signatures
    # because they point at collections that don't exist.
    reconcile_resume_index_state()
    row = _row(test_db, 1)
    assert row["last_index_signature"] is None
