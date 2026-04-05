import sqlite3
import pytest
from unittest.mock import patch

from src.memory.embedding_state import (
    get_active_signature,
    set_active_signature,
    ensure_row,
)


@pytest.fixture
def test_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE embedding_state ("
        "id INTEGER PRIMARY KEY, "
        "active_signature TEXT, "
        "updated_at TEXT DEFAULT (datetime('now')))"
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture(autouse=True)
def mock_db(test_db, monkeypatch):
    def make_conn():
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        return conn
    monkeypatch.setattr("src.memory.embedding_state.get_connection", make_conn)
    yield


def test_get_active_signature_returns_none_when_empty():
    ensure_row()
    assert get_active_signature() is None


def test_ensure_row_is_idempotent():
    ensure_row()
    ensure_row()
    # Still exactly one row
    assert get_active_signature() is None


def test_set_and_get_active_signature():
    ensure_row()
    set_active_signature("openai__text_embedding_3_small")
    assert get_active_signature() == "openai__text_embedding_3_small"


def test_set_active_signature_updates_value_across_calls():
    ensure_row()
    set_active_signature("sig_a")
    set_active_signature("sig_b")
    assert get_active_signature() == "sig_b"


def test_set_active_signature_to_none():
    ensure_row()
    set_active_signature("sig_a")
    set_active_signature(None)
    assert get_active_signature() is None
