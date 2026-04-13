import sqlite3
from unittest.mock import patch

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
        CREATE TABLE pipeline_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_run_id TEXT,
            job_id INTEGER,
            graph TEXT,
            node_name TEXT,
            step_type TEXT,
            status TEXT DEFAULT 'running',
            attempt INTEGER DEFAULT 1,
            version INTEGER DEFAULT 1,
            round_number INTEGER NOT NULL DEFAULT 0,
            run_id INTEGER,
            error TEXT,
            traceback TEXT,
            started_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT,
            duration_ms INTEGER
        );
        INSERT INTO ai_runs (id, job_id, resume_id, status) VALUES (1, 1, 1, 'running');
        """
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("JOBTRACKER_DB_PATH", db_path)
    return db_path


async def test_pipeline_events_stamps_round_number(test_db):
    """Inserting a pipeline_events row with round_number stores it correctly."""
    conn = sqlite3.connect(test_db)
    conn.execute(
        "INSERT INTO pipeline_events "
        "(workflow_run_id, run_id, step_type, graph, node_name, status, version, round_number) "
        "VALUES ('test-run', 1, 'jd_analysis', 'resume', 'jd_analysis', 'running', 1, 2)"
    )
    conn.commit()
    row = conn.execute(
        "SELECT status, round_number FROM pipeline_events "
        "WHERE run_id = 1 AND graph = 'resume' AND step_type = 'jd_analysis'"
    ).fetchone()
    conn.close()
    assert row == ("running", 2)


async def test_pipeline_events_stamps_round_on_new_version(test_db):
    """A second run of the same step inserts a new version row with the new round_number."""
    conn = sqlite3.connect(test_db)
    # First run: version=1, round_number=0
    conn.execute(
        "INSERT INTO pipeline_events "
        "(workflow_run_id, run_id, step_type, graph, node_name, status, version, round_number) "
        "VALUES ('test-run', 1, 'jd_analysis', 'resume', 'jd_analysis', 'completed', 1, 0)"
    )
    # Second run: version=2, round_number=1
    conn.execute(
        "INSERT INTO pipeline_events "
        "(workflow_run_id, run_id, step_type, graph, node_name, status, version, round_number) "
        "VALUES ('test-run', 1, 'jd_analysis', 'resume', 'jd_analysis', 'running', 2, 1)"
    )
    conn.commit()
    rows = conn.execute(
        "SELECT version, round_number, status FROM pipeline_events "
        "WHERE run_id = 1 AND graph = 'resume' AND step_type = 'jd_analysis' ORDER BY version"
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
    assert "workflow_run_id" in state
