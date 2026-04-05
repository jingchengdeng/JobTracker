import sqlite3
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.models.schemas import ClassifierOutput


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE jobs (id INTEGER PRIMARY KEY, description TEXT);
        CREATE TABLE resumes (id INTEGER PRIMARY KEY, extracted_text TEXT);
        CREATE TABLE ai_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER, resume_id INTEGER,
            status TEXT, conversation_summary TEXT, error TEXT,
            created_at TEXT DEFAULT (datetime('now')), completed_at TEXT
        );
        CREATE TABLE ai_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, step_type TEXT,
            status TEXT, result TEXT, version INTEGER DEFAULT 1,
            round_number INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')), completed_at TEXT
        );
        CREATE TABLE ai_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, role TEXT,
            content TEXT, round_number INTEGER, created_at TEXT DEFAULT (datetime('now'))
        );
        INSERT INTO jobs (id, description) VALUES (1, 'jd');
        INSERT INTO resumes (id, extracted_text) VALUES (1, 'resume');
        INSERT INTO ai_runs (id, job_id, resume_id, status) VALUES (1, 1, 1, 'completed');
        INSERT INTO ai_steps (run_id, step_type, status, result, round_number)
            VALUES (1, 'rewrite', 'completed', '{"rewritten_resume": "v1"}', 0);
        INSERT INTO ai_messages (run_id, role, content, round_number)
            VALUES (1, 'user', 'initial', 0);
        """
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("JOBTRACKER_DB_PATH", db_path)
    return db_path


def _wait_for_background(mock_pipeline, timeout=2.0):
    """Poll until the background thread has called run_pipeline (or timeout)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if mock_pipeline.called:
            return
        time.sleep(0.05)


def test_followup_saves_user_and_ack_with_same_round(test_db):
    fake_classifier = ClassifierOutput(
        needs_jd_analysis=False, needs_gap_analysis=False,
        needs_suggestions=True, needs_rewrite=True,
        reasoning="x",
        response_message="Sure, I'll tighten the rewrite.",
    )
    with patch("src.api.routes.classify_followup", return_value=fake_classifier), \
         patch("src.api.routes.run_pipeline") as mock_pipeline, \
         patch("src.api.routes.get_chat_model"), \
         patch("src.api.routes.summarize_old_rounds"):
        mock_pipeline.return_value = {}
        client = TestClient(app)
        resp = client.post("/api/runs/1/message", json={"content": "add leadership"})
        assert resp.status_code == 200
        _wait_for_background(mock_pipeline)

        conn = sqlite3.connect(test_db)
        msgs = conn.execute(
            "SELECT role, content, round_number FROM ai_messages WHERE run_id = 1 ORDER BY id"
        ).fetchall()
        conn.close()

        assert msgs[1] == ("user", "add leadership", 1)
        assert msgs[2] == ("assistant", "Sure, I'll tighten the rewrite.", 1)

        mock_pipeline.assert_called_once()
        call_kwargs = mock_pipeline.call_args.kwargs
        assert call_kwargs["needs_suggestions"] is True
        assert call_kwargs["needs_rewrite"] is True
        assert call_kwargs["needs_jd_analysis"] is False
        assert call_kwargs["needs_gap_analysis"] is False


def test_followup_falls_back_when_classifier_fails(test_db):
    with patch("src.api.routes.classify_followup", side_effect=Exception("boom")), \
         patch("src.api.routes.run_pipeline") as mock_pipeline, \
         patch("src.api.routes.get_chat_model"), \
         patch("src.api.routes.summarize_old_rounds"):
        mock_pipeline.return_value = {}
        client = TestClient(app)
        resp = client.post("/api/runs/1/message", json={"content": "add leadership"})
        assert resp.status_code == 200
        _wait_for_background(mock_pipeline)

        conn = sqlite3.connect(test_db)
        msgs = conn.execute(
            "SELECT role, content FROM ai_messages WHERE run_id = 1 AND round_number = 1 ORDER BY id"
        ).fetchall()
        conn.close()
        assert msgs[0] == ("user", "add leadership")
        assert msgs[1] == ("assistant", "Working on your refine...")
