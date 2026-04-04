import sqlite3
import pytest
from unittest.mock import patch

from src.memory.preferences import load_all_preferences
from src.memory.conversation import (
    save_message,
    get_recent_messages,
    get_current_round,
)


@pytest.fixture
def test_db(tmp_path):
    """Create a temporary test database with schema."""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE user_preferences (id INTEGER PRIMARY KEY, content TEXT, created_at TEXT DEFAULT (datetime('now')))"
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
    return db_path


@pytest.fixture(autouse=True)
def mock_db(test_db):
    with patch("src.memory.preferences.get_connection") as mock_pref, \
         patch("src.memory.conversation.get_connection") as mock_conv:
        def make_conn():
            conn = sqlite3.connect(test_db)
            conn.row_factory = sqlite3.Row
            return conn
        mock_pref.side_effect = make_conn
        mock_conv.side_effect = make_conn
        yield test_db


def test_load_preferences_empty(mock_db):
    prefs = load_all_preferences()
    assert prefs == []


def test_load_preferences_with_data(mock_db):
    conn = sqlite3.connect(mock_db)
    conn.execute("INSERT INTO user_preferences (content) VALUES ('Use STAR format')")
    conn.execute("INSERT INTO user_preferences (content) VALUES ('Keep it concise')")
    conn.commit()
    conn.close()

    prefs = load_all_preferences()
    assert len(prefs) == 2
    assert "Use STAR format" in prefs


def test_save_and_get_messages(mock_db):
    conn = sqlite3.connect(mock_db)
    conn.execute("INSERT INTO ai_runs (id, job_id, resume_id) VALUES (1, 1, 1)")
    conn.commit()
    conn.close()

    save_message(1, "user", "Analyze this resume", 1)
    save_message(1, "assistant", "Here is the analysis...", 1)

    messages = get_recent_messages(1)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


def test_get_current_round(mock_db):
    conn = sqlite3.connect(mock_db)
    conn.execute("INSERT INTO ai_runs (id, job_id, resume_id) VALUES (1, 1, 1)")
    conn.commit()
    conn.close()

    assert get_current_round(1) == 1

    save_message(1, "user", "Hello", 1)
    assert get_current_round(1) == 2
