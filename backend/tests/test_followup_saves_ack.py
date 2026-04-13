import asyncio
import sqlite3
from unittest.mock import patch, AsyncMock

import pytest
from httpx import AsyncClient, ASGITransport

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
        CREATE TABLE pipeline_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_run_id TEXT NOT NULL,
            job_id INTEGER,
            graph TEXT NOT NULL,
            node_name TEXT NOT NULL,
            status TEXT NOT NULL,
            attempt INTEGER NOT NULL DEFAULT 1,
            started_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT,
            duration_ms INTEGER,
            error TEXT,
            traceback TEXT,
            run_id INTEGER,
            step_type TEXT,
            result TEXT,
            version INTEGER NOT NULL DEFAULT 1,
            round_number INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE ai_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, role TEXT,
            content TEXT, round_number INTEGER, created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS interview_sessions (
            id INTEGER PRIMARY KEY, status TEXT, ended_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS linkedin_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'running',
            company_domain TEXT,
            company_data_json TEXT,
            company_summary TEXT,
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS embedding_state (
            id INTEGER PRIMARY KEY,
            active_signature TEXT,
            pending_signature TEXT,
            updated_at TEXT
        );
        INSERT INTO jobs (id, description) VALUES (1, 'jd');
        INSERT INTO resumes (id, extracted_text) VALUES (1, 'resume');
        INSERT INTO ai_runs (id, job_id, resume_id, status) VALUES (1, 1, 1, 'completed');
        INSERT INTO pipeline_events (
            workflow_run_id, graph, node_name, status,
            run_id, step_type, result, version, round_number
        ) VALUES (
            'wr-test', 'resume', 'rewrite', 'completed',
            1, 'rewrite', '{"rewritten_resume": "v1"}', 1, 0
        );
        INSERT INTO ai_messages (run_id, role, content, round_number)
            VALUES (1, 'user', 'initial', 0);
        """
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("JOBTRACKER_DB_PATH", db_path)
    return db_path


@pytest.mark.asyncio
async def test_followup_saves_user_and_ack_with_same_round(test_db):
    fake_classifier = ClassifierOutput(
        needs_jd_analysis=False, needs_gap_analysis=False,
        needs_suggestions=True, needs_rewrite=True,
        reasoning="x",
        response_message="Sure, I'll tighten the rewrite.",
    )
    mock_classifier = AsyncMock(return_value=fake_classifier)
    mock_pipeline = AsyncMock(return_value={})
    mock_summarize = AsyncMock()

    with patch("src.api.routes.classify_followup", mock_classifier), \
         patch("src.api.routes.run_pipeline", mock_pipeline), \
         patch("src.api.routes.get_chat_model"), \
         patch("src.api.routes.summarize_old_rounds", mock_summarize):
        import src.api.routes as routes_mod
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/runs/1/message", json={"content": "add leadership"})
            assert resp.status_code == 200
            # Wait for all background tasks to complete
            if routes_mod._background_tasks:
                await asyncio.gather(*list(routes_mod._background_tasks), return_exceptions=True)

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


@pytest.mark.asyncio
async def test_followup_falls_back_when_classifier_fails(test_db):
    mock_classifier = AsyncMock(side_effect=Exception("boom"))
    mock_pipeline = AsyncMock(return_value={})
    mock_summarize = AsyncMock()

    with patch("src.api.routes.classify_followup", mock_classifier), \
         patch("src.api.routes.run_pipeline", mock_pipeline), \
         patch("src.api.routes.get_chat_model"), \
         patch("src.api.routes.summarize_old_rounds", mock_summarize):
        import src.api.routes as routes_mod
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/runs/1/message", json={"content": "add leadership"})
            assert resp.status_code == 200
            # Wait for all background tasks to complete
            if routes_mod._background_tasks:
                await asyncio.gather(*list(routes_mod._background_tasks), return_exceptions=True)

        conn = sqlite3.connect(test_db)
        msgs = conn.execute(
            "SELECT role, content FROM ai_messages WHERE run_id = 1 AND round_number = 1 ORDER BY id"
        ).fetchall()
        conn.close()
        assert msgs[0] == ("user", "add leadership")
        assert msgs[1] == ("assistant", "Working on your refine...")
