import sqlite3
from unittest.mock import AsyncMock

import pytest

from src.memory.preferences import load_all_preferences
from src.memory.conversation import (
    save_message,
    get_recent_messages,
    get_current_round,
    get_conversation_summary,
    summarize_old_rounds,
    MAX_RAW_ROUNDS,
)


@pytest.fixture(autouse=True)
def test_db(tmp_path, monkeypatch):
    """Create a temporary test database with schema and point get_connection at it."""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE user_preferences (id INTEGER PRIMARY KEY, content TEXT, "
        "created_at TEXT DEFAULT (datetime('now')))"
    )
    conn.execute(
        "CREATE TABLE ai_runs (id INTEGER PRIMARY KEY, job_id INTEGER, resume_id INTEGER, "
        "status TEXT DEFAULT 'pending', conversation_summary TEXT, error TEXT, "
        "created_at TEXT DEFAULT (datetime('now')), completed_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE ai_messages (id INTEGER PRIMARY KEY, run_id INTEGER, role TEXT, "
        "content TEXT, round_number INTEGER, created_at TEXT DEFAULT (datetime('now')))"
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("JOBTRACKER_DB_PATH", db_path)
    return db_path


async def test_load_preferences_empty(test_db):
    prefs = await load_all_preferences()
    assert prefs == []


async def test_load_preferences_with_data(test_db):
    conn = sqlite3.connect(test_db)
    conn.execute("INSERT INTO user_preferences (content) VALUES ('Use STAR format')")
    conn.execute("INSERT INTO user_preferences (content) VALUES ('Keep it concise')")
    conn.commit()
    conn.close()

    prefs = await load_all_preferences()
    assert len(prefs) == 2
    assert "Use STAR format" in prefs


async def test_save_and_get_messages(test_db):
    conn = sqlite3.connect(test_db)
    conn.execute("INSERT INTO ai_runs (id, job_id, resume_id) VALUES (1, 1, 1)")
    conn.commit()
    conn.close()

    await save_message(1, "user", "Analyze this resume", 1)
    await save_message(1, "assistant", "Here is the analysis...", 1)

    messages = await get_recent_messages(1)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


async def test_get_current_round(test_db):
    conn = sqlite3.connect(test_db)
    conn.execute("INSERT INTO ai_runs (id, job_id, resume_id) VALUES (1, 1, 1)")
    conn.commit()
    conn.close()

    assert await get_current_round(1) == 1

    await save_message(1, "user", "Hello", 1)
    assert await get_current_round(1) == 2


async def test_get_conversation_summary_none(test_db):
    assert await get_conversation_summary(999) is None


async def test_get_conversation_summary_exists(test_db):
    conn = sqlite3.connect(test_db)
    conn.execute(
        "INSERT INTO ai_runs (id, job_id, resume_id, conversation_summary) "
        "VALUES (1, 1, 1, 'previous summary text')"
    )
    conn.commit()
    conn.close()

    summary = await get_conversation_summary(1)
    assert summary == "previous summary text"


async def test_get_recent_messages_empty(test_db):
    messages = await get_recent_messages(999)
    assert messages == []


async def test_get_recent_messages_respects_max_rounds(test_db):
    conn = sqlite3.connect(test_db)
    conn.execute("INSERT INTO ai_runs (id, job_id, resume_id) VALUES (1, 1, 1)")
    conn.commit()
    conn.close()

    # Insert messages across 5 rounds
    for rnd in range(1, 6):
        await save_message(1, "user", f"Question round {rnd}", rnd)
        await save_message(1, "assistant", f"Answer round {rnd}", rnd)

    messages = await get_recent_messages(1)
    # Should only contain the last MAX_RAW_ROUNDS rounds (3, 4, 5)
    rounds_in_result = set()
    for msg in messages:
        for rnd in range(1, 6):
            if str(rnd) in msg["content"]:
                rounds_in_result.add(rnd)
    assert rounds_in_result == {3, 4, 5}


async def test_summarize_old_rounds_noop_when_few_rounds(test_db):
    """No summarization when rounds <= MAX_RAW_ROUNDS."""
    conn = sqlite3.connect(test_db)
    conn.execute("INSERT INTO ai_runs (id, job_id, resume_id) VALUES (1, 1, 1)")
    conn.commit()
    conn.close()

    for rnd in range(1, MAX_RAW_ROUNDS + 1):
        await save_message(1, "user", f"msg {rnd}", rnd)

    mock_llm = AsyncMock()
    await summarize_old_rounds(1, mock_llm)

    # LLM should never be called
    mock_llm.ainvoke.assert_not_called()


async def test_summarize_old_rounds_summarizes_and_deletes(test_db):
    """When rounds exceed MAX_RAW_ROUNDS, old rounds get summarized and deleted."""
    conn = sqlite3.connect(test_db)
    conn.execute("INSERT INTO ai_runs (id, job_id, resume_id) VALUES (1, 1, 1)")
    conn.commit()
    conn.close()

    # Create 5 rounds of messages (exceeds MAX_RAW_ROUNDS=3)
    for rnd in range(1, 6):
        await save_message(1, "user", f"Question {rnd}", rnd)
        await save_message(1, "assistant", f"Answer {rnd}", rnd)

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AsyncMock(content="Summarized conversation")

    await summarize_old_rounds(1, mock_llm)

    # LLM was called once
    mock_llm.ainvoke.assert_called_once()

    # Conversation summary was saved
    summary = await get_conversation_summary(1)
    assert summary == "Summarized conversation"

    # Old rounds (1, 2) should be deleted; recent rounds (3, 4, 5) remain
    messages = await get_recent_messages(1)
    rounds_in_result = set()
    for msg in messages:
        for rnd in range(1, 6):
            if str(rnd) in msg["content"]:
                rounds_in_result.add(rnd)
    assert 1 not in rounds_in_result
    assert 2 not in rounds_in_result
    assert {3, 4, 5}.issubset(rounds_in_result)
