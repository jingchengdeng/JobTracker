import sqlite3
import pytest

from src.memory.embedding_state import (
    get_active_signature,
    set_active_signature,
    ensure_row,
)


@pytest.fixture
def test_db(tmp_path, monkeypatch):
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
    monkeypatch.setenv("JOBTRACKER_DB_PATH", db_path)
    return db_path


async def test_get_active_signature_returns_none_when_empty(test_db):
    await ensure_row()
    assert await get_active_signature() is None


async def test_ensure_row_is_idempotent(test_db):
    await ensure_row()
    await ensure_row()
    # Still exactly one row
    assert await get_active_signature() is None


async def test_set_and_get_active_signature(test_db):
    await ensure_row()
    await set_active_signature("openai__text_embedding_3_small")
    assert await get_active_signature() == "openai__text_embedding_3_small"


async def test_set_active_signature_updates_value_across_calls(test_db):
    await ensure_row()
    await set_active_signature("sig_a")
    await set_active_signature("sig_b")
    assert await get_active_signature() == "sig_b"


async def test_set_active_signature_to_none(test_db):
    await ensure_row()
    await set_active_signature("sig_a")
    await set_active_signature(None)
    assert await get_active_signature() is None
