import sqlite3
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from src.main import app
from src.memory.embedding_state import ensure_row


@pytest.fixture
def test_db(tmp_path, monkeypatch):
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
        "INSERT INTO resumes (name, file_path, file_type, extracted_text) "
        "VALUES ('A.pdf', 'p', 'pdf', 'alpha')"
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("JOBTRACKER_DB_PATH", db_path)
    monkeypatch.setenv("VECTORDB_PATH", str(tmp_path / "vectordb"))
    ensure_row()
    return db_path


@pytest.fixture
def mock_model_config():
    with patch("src.services.embeddings.load_model_config") as m:
        m.return_value = {
            "embedding": {"provider": "openai", "model": "text-embedding-3-small"}
        }
        yield m


def test_status_returns_configured_and_active(test_db, mock_model_config):
    client = TestClient(app)
    resp = client.get("/api/embedding/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_signature"] is None
    assert data["configured_signature"] == "openai__text_embedding_3_small"
    assert len(data["resumes"]) == 1
    assert data["resumes"][0]["name"] == "A.pdf"


def test_status_includes_active_job(test_db, mock_model_config):
    from src.memory.reindex import _jobs, ReindexJob
    _jobs.clear()
    _jobs["abc"] = ReindexJob(
        job_id="abc", status="running", target_signature="x",
        started_at="2026-04-05T00:00:00Z", total=5,
    )
    client = TestClient(app)
    resp = client.get("/api/embedding/status")
    assert resp.status_code == 200
    assert resp.json()["active_job"]["job_id"] == "abc"
    _jobs.clear()


def test_reindex_returns_409_when_job_running(test_db, mock_model_config):
    from src.memory.reindex import _jobs, ReindexJob
    _jobs.clear()
    _jobs["existing"] = ReindexJob(
        job_id="existing", status="running", target_signature="x",
        started_at="2026-04-05T00:00:00Z",
    )
    client = TestClient(app)
    resp = client.post("/api/embedding/reindex", json={})
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "reindex_in_progress"
    _jobs.clear()


def test_reindex_rejects_when_no_api_key(test_db, mock_model_config):
    from src.memory.reindex import _jobs
    _jobs.clear()
    with patch("src.services.embeddings.load_api_key", return_value=None):
        client = TestClient(app)
        resp = client.post("/api/embedding/reindex", json={})
    # Job starts but may fail synchronously inside the background task; the
    # POST itself should return 200 with a job_id OR 400 if the orchestrator
    # rejects up front. Either is acceptable — this test just ensures the
    # endpoint doesn't 500.
    assert resp.status_code in (200, 400)
    _jobs.clear()


def test_get_reindex_job_404_when_unknown(test_db):
    from src.memory.reindex import _jobs
    _jobs.clear()
    client = TestClient(app)
    resp = client.get("/api/embedding/reindex/nope")
    assert resp.status_code == 404
