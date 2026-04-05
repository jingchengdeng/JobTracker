import sqlite3
import pytest
from unittest.mock import patch

from src.memory.collection_resolver import (
    active_collection,
    collection_for_signature,
)
from src.memory.embedding_state import set_active_signature, ensure_row


@pytest.fixture
def test_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE embedding_state ("
        "id INTEGER PRIMARY KEY, active_signature TEXT, updated_at TEXT)"
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture(autouse=True)
def mock_db_and_vectordb(test_db, tmp_path, monkeypatch):
    monkeypatch.setenv("VECTORDB_PATH", str(tmp_path / "vectordb"))
    fake_config = {
        "embedding": {"provider": "sentence_transformer", "model": "all-MiniLM-L6-v2"}
    }
    def make_conn():
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        return conn
    monkeypatch.setattr("src.memory.embedding_state.get_connection", make_conn)
    with patch("src.memory.collection_resolver.load_model_config", return_value=fake_config):
        ensure_row()
        yield


def test_active_collection_returns_none_when_no_active_signature():
    assert active_collection() is None


def test_collection_for_signature_creates_collection():
    col = collection_for_signature(
        "sentence_transformer__all_minilm_l6_v2",
        provider="sentence_transformer",
        model="all-MiniLM-L6-v2",
    )
    assert col is not None
    assert col.name == "resume_chunks__sentence_transformer__all_minilm_l6_v2"


def test_active_collection_returns_collection_for_active_signature():
    set_active_signature("sentence_transformer__all_minilm_l6_v2")
    col = active_collection()
    assert col is not None
    assert col.name == "resume_chunks__sentence_transformer__all_minilm_l6_v2"


def test_collection_for_signature_is_idempotent():
    col1 = collection_for_signature(
        "sentence_transformer__all_minilm_l6_v2",
        provider="sentence_transformer",
        model="all-MiniLM-L6-v2",
    )
    col2 = collection_for_signature(
        "sentence_transformer__all_minilm_l6_v2",
        provider="sentence_transformer",
        model="all-MiniLM-L6-v2",
    )
    assert col1.name == col2.name
