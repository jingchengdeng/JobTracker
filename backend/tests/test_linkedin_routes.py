import asyncio
import pytest
import sqlite3
from unittest.mock import patch, AsyncMock


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "test.db")
    monkeypatch.setenv("JOBTRACKER_DB_PATH", path)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY, title TEXT, company TEXT, description TEXT)")
    conn.execute("INSERT INTO jobs (id, title, company, description) VALUES (1, 'SWE', 'Stripe', 'Build APIs')")
    conn.commit()
    conn.close()
    from src.agents.linkedin_db import ensure_linkedin_tables
    ensure_linkedin_tables(path)
    return path


@pytest.fixture
def client(db_path):
    from fastapi.testclient import TestClient
    from src.api.linkedin_routes import router
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestStartSearch:
    @patch("src.api.linkedin_routes.run_linkedin_pipeline", new_callable=AsyncMock)
    def test_returns_search_id(self, mock_pipeline, client):
        resp = client.post("/api/linkedin/search", json={"job_id": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert "search_id" in data
        assert data["status"] == "running"

    def test_invalid_job_id_returns_404(self, client):
        resp = client.post("/api/linkedin/search", json={"job_id": 999})
        assert resp.status_code == 404


class TestGetSearch:
    def test_get_running_search(self, client, db_path):
        from src.agents.linkedin_db import create_search
        search_id = asyncio.get_event_loop().run_until_complete(create_search(job_id=1))
        resp = client.get(f"/api/linkedin/{search_id}")
        assert resp.status_code == 200
        assert resp.json()["search"]["status"] == "running"

    def test_get_nonexistent_search(self, client):
        resp = client.get("/api/linkedin/999")
        assert resp.status_code == 404


class TestDeleteSearch:
    def test_delete_search(self, client, db_path):
        from src.agents.linkedin_db import create_search
        search_id = asyncio.get_event_loop().run_until_complete(create_search(job_id=1))
        resp = client.delete(f"/api/linkedin/{search_id}")
        assert resp.status_code == 200
        # Verify it is gone
        resp2 = client.get(f"/api/linkedin/{search_id}")
        assert resp2.status_code == 404
