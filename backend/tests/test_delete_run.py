import sqlite3
import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE ai_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER, resume_id INTEGER,
            status TEXT DEFAULT 'pending', conversation_summary TEXT, error TEXT,
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
        INSERT INTO ai_runs (id, job_id, resume_id, status)
            VALUES (1, 1, 1, 'completed'), (2, 1, 1, 'running');
        INSERT INTO pipeline_events (
            workflow_run_id, graph, node_name, status, run_id, step_type, result
        ) VALUES
            ('wr-1', 'resume', 'jd_analysis', 'completed', 1, 'jd_analysis', '{}'),
            ('wr-1', 'resume', 'gap_analysis', 'completed', 1, 'gap_analysis', '{}'),
            ('wr-2', 'resume', 'jd_analysis', 'running', 2, 'jd_analysis', NULL);
        INSERT INTO ai_messages (run_id, role, content, round_number)
            VALUES (1, 'user', 'hi', 1), (1, 'assistant', 'hello', 1);
        """
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("JOBTRACKER_DB_PATH", db_path)
    return db_path


def _counts(db_path, run_id):
    conn = sqlite3.connect(db_path)
    runs = conn.execute("SELECT COUNT(*) FROM ai_runs WHERE id = ?", (run_id,)).fetchone()[0]
    steps = conn.execute(
        "SELECT COUNT(*) FROM pipeline_events WHERE run_id = ? AND graph = 'resume'",
        (run_id,),
    ).fetchone()[0]
    msgs = conn.execute("SELECT COUNT(*) FROM ai_messages WHERE run_id = ?", (run_id,)).fetchone()[0]
    conn.close()
    return runs, steps, msgs


def test_delete_cascades_steps_and_messages(test_db):
    assert _counts(test_db, 1) == (1, 2, 2)
    client = TestClient(app)
    resp = client.delete("/api/runs/1")
    assert resp.status_code == 204
    assert _counts(test_db, 1) == (0, 0, 0)


def test_delete_returns_409_for_running_run(test_db):
    client = TestClient(app)
    resp = client.delete("/api/runs/2")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "run_in_progress"
    assert _counts(test_db, 2) == (1, 1, 0)


def test_delete_returns_404_for_unknown_run(test_db):
    client = TestClient(app)
    resp = client.delete("/api/runs/999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Run not found"


def test_delete_does_not_touch_other_runs(test_db):
    client = TestClient(app)
    client.delete("/api/runs/1")
    assert _counts(test_db, 2) == (1, 1, 0)
