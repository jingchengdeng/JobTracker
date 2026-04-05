"""Tests for per-resume state persistence in the RAG indexing path.

When a resume is uploaded and indexed via /api/extract-text, `index_resume`
must persist the resume's index signature and status to the SQLite row so
that the Resumes-tab badge and banner reflect reality.
"""
import sqlite3
from unittest.mock import patch

import pytest

from src.memory.embedding_state import ensure_row, set_active_signature
from src.memory.rag import index_resume


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
        "VALUES (7, 'A.pdf', 'p', 'pdf', 'alpha')"
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture(autouse=True)
def wire_db(test_db, monkeypatch):
    def make_conn():
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        return conn
    monkeypatch.setattr("src.memory.embedding_state.get_connection", make_conn)
    monkeypatch.setattr("src.memory.rag.get_connection", make_conn)
    ensure_row()
    yield


def _read_row(db_path: str, resume_id: int) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT last_index_signature, last_index_status, last_index_error "
            "FROM resumes WHERE id = ?",
            (resume_id,),
        ).fetchone()
    finally:
        conn.close()
    return dict(row)


def test_index_resume_marks_row_ok_on_success(test_db):
    set_active_signature("openai__m")
    with patch("src.memory.rag.active_collection") as ac, \
         patch("src.memory.rag.index_resume_into") as into:
        ac.return_value = object()  # any truthy collection
        into.return_value = None

        index_resume(7, "A.pdf", "alpha text")

    row = _read_row(test_db, 7)
    assert row["last_index_signature"] == "openai__m"
    assert row["last_index_status"] == "ok"
    assert row["last_index_error"] is None


def test_index_resume_marks_failed_when_chroma_raises(test_db):
    set_active_signature("openai__m")
    with patch("src.memory.rag.active_collection") as ac, \
         patch("src.memory.rag.index_resume_into") as into:
        ac.return_value = object()
        into.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError):
            index_resume(7, "A.pdf", "alpha text")

    row = _read_row(test_db, 7)
    assert row["last_index_status"] == "failed"
    assert "boom" in row["last_index_error"]


def test_index_resume_noop_when_no_active_signature(test_db):
    # Active signature still NULL — no indexing happens, row stays clean
    with patch("src.memory.rag.active_collection") as ac:
        ac.return_value = None
        index_resume(7, "A.pdf", "alpha")

    row = _read_row(test_db, 7)
    assert row["last_index_signature"] is None
    assert row["last_index_status"] is None
