import json
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
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT
        );
        CREATE TABLE resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, version TEXT,
            file_path TEXT, file_type TEXT, extracted_text TEXT
        );
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
        INSERT INTO jobs (id, title, description) VALUES (1, 'Sr BE', 'desc');
        INSERT INTO resumes (id, name, version, file_path, file_type, extracted_text)
            VALUES (10, 'AI Engineer Resume', 'v2', 'p', 'pdf', 't'),
                   (11, 'Backend Resume', 'v1', 'p', 'pdf', 't');
        """
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("JOBTRACKER_DB_PATH", db_path)
    return db_path


def _insert_run(db_path, run_id, resume_id, status, created_at, gap_result=None):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO ai_runs (id, job_id, resume_id, status, created_at) "
        "VALUES (?, 1, ?, ?, ?)",
        (run_id, resume_id, status, created_at),
    )
    if gap_result is not None:
        conn.execute(
            "INSERT INTO pipeline_events ("
            "workflow_run_id, graph, node_name, status, run_id, step_type, "
            "result, version, round_number"
            ") VALUES ('wr-test', 'resume', 'gap_analysis', 'completed', ?, "
            "'gap_analysis', ?, 1, 0)",
            (run_id, gap_result),
        )
    conn.commit()
    conn.close()


def test_list_returns_runs_newest_first(test_db):
    _insert_run(test_db, 1, 10, "completed", "2026-04-05T10:00:00")
    _insert_run(test_db, 2, 11, "completed", "2026-04-05T11:00:00")
    _insert_run(test_db, 3, 10, "running", "2026-04-05T12:00:00")

    client = TestClient(app)
    resp = client.get("/api/jobs/1/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert [r["id"] for r in data] == [3, 2, 1]


def test_list_includes_resume_name_and_version(test_db):
    _insert_run(test_db, 1, 10, "completed", "2026-04-05T10:00:00")
    client = TestClient(app)
    data = client.get("/api/jobs/1/runs").json()
    assert data[0]["resume_name"] == "AI Engineer Resume"
    assert data[0]["resume_version"] == "v2"
    assert data[0]["resume_id"] == 10


def test_list_extracts_match_score_from_gap_analysis(test_db):
    gap = json.dumps({"overall_match_score": 82, "items": []})
    _insert_run(test_db, 1, 10, "completed", "2026-04-05T10:00:00", gap_result=gap)
    client = TestClient(app)
    data = client.get("/api/jobs/1/runs").json()
    assert data[0]["match_score"] == 82


def test_list_match_score_null_when_no_gap_step(test_db):
    _insert_run(test_db, 1, 10, "running", "2026-04-05T10:00:00")
    client = TestClient(app)
    data = client.get("/api/jobs/1/runs").json()
    assert data[0]["match_score"] is None


def test_list_match_score_null_when_gap_result_malformed(test_db):
    _insert_run(test_db, 1, 10, "completed", "2026-04-05T10:00:00", gap_result="not json")
    client = TestClient(app)
    data = client.get("/api/jobs/1/runs").json()
    assert data[0]["match_score"] is None


def test_list_match_score_null_when_gap_result_missing_key(test_db):
    gap = json.dumps({"items": []})
    _insert_run(test_db, 1, 10, "completed", "2026-04-05T10:00:00", gap_result=gap)
    client = TestClient(app)
    data = client.get("/api/jobs/1/runs").json()
    assert data[0]["match_score"] is None


def test_list_empty_for_job_with_no_runs(test_db):
    client = TestClient(app)
    resp = client.get("/api/jobs/1/runs")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_run_response_shape_matches_legacy_ai_steps_contract(test_db):
    """The resume-tailor frontend reads these exact fields. Ensure pipeline_events
    query returns a compatible payload."""
    conn = sqlite3.connect(test_db)
    conn.execute(
        "INSERT INTO ai_runs (id, job_id, resume_id, status, created_at) "
        "VALUES (1, 1, 10, 'completed', '2026-04-05T10:00:00')"
    )
    conn.execute(
        "INSERT INTO pipeline_events ("
        "workflow_run_id, graph, node_name, status, run_id, step_type, "
        "version, round_number, result"
        ") VALUES ('wr-1', 'resume', 'jd_analysis', 'completed', 1, "
        "'jd_analysis', 1, 0, 'R')"
    )
    conn.commit()
    conn.close()

    client = TestClient(app)
    resp = client.get("/api/runs/1")
    assert resp.status_code == 200
    data = resp.json()
    steps = data["steps"]
    assert len(steps) == 1
    step = steps[0]
    expected_keys = {
        "id", "run_id", "step_type", "status", "result",
        "version", "round_number", "created_at", "completed_at",
    }
    assert set(step.keys()) == expected_keys
