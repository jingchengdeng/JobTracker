import sqlite3
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE ai_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER, resume_id INTEGER,
            status TEXT DEFAULT 'pending', error TEXT,
            created_at TEXT DEFAULT (datetime('now')), completed_at TEXT
        );
        CREATE TABLE ai_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, step_type TEXT,
            status TEXT DEFAULT 'pending', result TEXT,
            version INTEGER DEFAULT 1, round_number INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')), completed_at TEXT
        );
        INSERT INTO ai_runs (id, job_id, resume_id, status) VALUES (1, 1, 1, 'running');
        """
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("JOBTRACKER_DB_PATH", db_path)
    return db_path


async def test_update_step_status_stamps_round_number(test_db):
    from src.agents.orchestrator import _update_step_status
    await _update_step_status(1, "jd_analysis", "running", round_number=2)
    conn = sqlite3.connect(test_db)
    row = conn.execute(
        "SELECT status, round_number FROM ai_steps WHERE run_id = 1 AND step_type = 'jd_analysis'"
    ).fetchone()
    conn.close()
    assert row == ("running", 2)


async def test_update_step_status_stamps_round_on_new_version(test_db):
    from src.agents.orchestrator import _update_step_status
    await _update_step_status(1, "jd_analysis", "running", round_number=0)
    await _update_step_status(1, "jd_analysis", "completed", result="r1", round_number=0)
    await _update_step_status(1, "jd_analysis", "running", round_number=1)
    conn = sqlite3.connect(test_db)
    rows = conn.execute(
        "SELECT version, round_number, status FROM ai_steps "
        "WHERE run_id = 1 AND step_type = 'jd_analysis' ORDER BY version"
    ).fetchall()
    conn.close()
    assert rows == [(1, 0, "completed"), (2, 1, "running")]


async def test_run_pipeline_accepts_explicit_booleans(test_db):
    """run_pipeline no longer calls classify_followup; callers pass booleans."""
    from src.agents import orchestrator
    captured = {}

    async def fake_ainvoke(state):
        captured["state"] = state
        return {**state, "jd_analysis": "done"}

    with patch.object(orchestrator, "workflow") as mock_wf:
        mock_wf.ainvoke = fake_ainvoke
        await orchestrator.run_pipeline(
            run_id=1, job_id=1, resume_id=1,
            jd_text="jd", resume_text="rt",
            round_number=3,
            needs_jd_analysis=False,
            needs_gap_analysis=True,
            needs_suggestions=False,
            needs_rewrite=True,
        )
    state = captured["state"]
    assert state["round_number"] == 3
    assert state["needs_jd_analysis"] is False
    assert state["needs_gap_analysis"] is True
    assert state["needs_suggestions"] is False
    assert state["needs_rewrite"] is True
