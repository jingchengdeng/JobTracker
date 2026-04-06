import sqlite3
import json
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from tests.test_interview_db import _create_tables


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    _create_tables(db_path)
    monkeypatch.setenv("JOBTRACKER_DB_PATH", db_path)
    return db_path


@pytest.fixture
def client(test_db):
    from src.main import app
    return TestClient(app)


class TestStartInterview:
    @patch("src.api.interview_routes.run_planning")
    @patch("src.api.interview_routes.load_credential")
    def test_start_creates_session(self, mock_cred, mock_plan, client):
        mock_cred.return_value = {"type": "api_key", "key": "fake"}
        mock_plan.return_value = None

        resp = client.post("/api/interview/start", json={
            "job_id": 1, "resume_id": 1, "interview_type": "technical",
            "difficulty": "medium", "duration_minutes": 30, "voice": "nova",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert "ws_url" in data

    @patch("src.api.interview_routes.load_credential")
    def test_start_rejects_missing_openai_key(self, mock_cred, client):
        mock_cred.return_value = None

        resp = client.post("/api/interview/start", json={
            "job_id": 1, "resume_id": 1, "interview_type": "technical",
            "difficulty": "medium", "duration_minutes": 30, "voice": "nova",
        })
        assert resp.status_code == 400
        assert "OpenAI API key required" in resp.json()["detail"]


class TestEndInterview:
    @patch("src.api.interview_routes.run_scoring")
    @patch("src.api.interview_routes.run_planning")
    @patch("src.api.interview_routes.load_credential")
    def test_end_triggers_scoring(self, mock_cred, mock_plan, mock_score, client):
        mock_cred.return_value = {"type": "api_key", "key": "fake"}
        mock_plan.return_value = None
        mock_score.return_value = None

        start_resp = client.post("/api/interview/start", json={
            "job_id": 1, "resume_id": 1, "interview_type": "technical",
            "difficulty": "medium", "duration_minutes": 30, "voice": "nova",
        })
        session_id = start_resp.json()["session_id"]

        end_resp = client.patch(f"/api/interview/{session_id}/end")
        assert end_resp.status_code == 200
        mock_score.assert_called_once_with(session_id)


class TestListSessions:
    @patch("src.api.interview_routes.run_planning")
    @patch("src.api.interview_routes.load_credential")
    def test_list_returns_sessions_for_job(self, mock_cred, mock_plan, client):
        mock_cred.return_value = {"type": "api_key", "key": "fake"}
        mock_plan.return_value = None

        client.post("/api/interview/start", json={
            "job_id": 1, "resume_id": 1, "interview_type": "technical",
            "difficulty": "medium", "duration_minutes": 30, "voice": "nova",
        })
        resp = client.get("/api/interview/sessions?job_id=1")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestGetSession:
    @patch("src.api.interview_routes.run_planning")
    @patch("src.api.interview_routes.load_credential")
    def test_get_returns_session_detail(self, mock_cred, mock_plan, client):
        mock_cred.return_value = {"type": "api_key", "key": "fake"}
        mock_plan.return_value = None

        start_resp = client.post("/api/interview/start", json={
            "job_id": 1, "resume_id": 1, "interview_type": "technical",
            "difficulty": "medium", "duration_minutes": 30, "voice": "nova",
        })
        session_id = start_resp.json()["session_id"]

        resp = client.get(f"/api/interview/{session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session"]["id"] == session_id


class TestDeleteSession:
    def test_delete_removes_session(self, client, test_db):
        from src.agents.interview_db import create_session, load_session

        session_id = create_session(
            job_id=1, resume_id=1, interview_type="technical",
            difficulty="medium", duration_minutes=30, voice="nova",
        )
        resp = client.delete(f"/api/interview/{session_id}")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        with pytest.raises(ValueError):
            load_session(session_id)

    def test_delete_nonexistent_returns_ok(self, client, test_db):
        resp = client.delete("/api/interview/99999")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
