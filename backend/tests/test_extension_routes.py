import os
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.extension_routes import router


@pytest.fixture
def extractions_dir(tmp_path):
    d = tmp_path / "extractions"
    d.mkdir()
    return d


@pytest.fixture
def client(extractions_dir, monkeypatch):
    monkeypatch.setenv("EXTRACTIONS_DIR", str(extractions_dir))
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


RAW_EXTRACTION_PAYLOAD = {
    "url": "https://www.linkedin.com/jobs/view/4369788254/",
    "extracted": {},
    "rawPanelText": "[field: company]\n[selector: test]\nKforce Inc\n\n---\n\n[field: description]\n[selector: test]\nAbout the job\n\nSome description here.",
    "timestamp": "2026-04-09T01-25-31",
}

VALID_PAYLOAD = {
    "url": "https://www.linkedin.com/jobs/view/123456/",
    "extracted": {
        "title": "Senior Software Engineer",
        "company": "Acme Corp",
        "description": "About the job. We are looking for a senior engineer...",
        "location": "Tampa, FL",
        "workMode": "Hybrid",
        "salary": "$150K/yr - $230K/yr",
        "jobType": "Full-time",
    },
    "rawPanelText": "Full raw text of the job panel goes here...",
    "timestamp": "2026-04-08T12-34-56",
}

_NOOP_PIPELINE = {"job_id": None, "error": None}


@patch("src.api.extension_routes.run_extraction_pipeline", new_callable=AsyncMock, return_value=_NOOP_PIPELINE)
class TestExtractEndpoint:
    def test_saves_file_and_returns_filename(self, mock_pipeline, client, extractions_dir):
        resp = client.post("/api/extension/extract", json=VALID_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["filename"].endswith(".txt")

        files = list(extractions_dir.iterdir())
        assert len(files) == 1
        content = files[0].read_text()
        assert "https://www.linkedin.com/jobs/view/123456/" in content
        assert "Senior Software Engineer" in content
        assert "Acme Corp" in content
        assert "Full raw text of the job panel goes here..." in content

    def test_file_contains_all_sections(self, mock_pipeline, client, extractions_dir):
        resp = client.post("/api/extension/extract", json=VALID_PAYLOAD)
        assert resp.status_code == 200
        files = list(extractions_dir.iterdir())
        content = files[0].read_text()
        assert "=== URL ===" in content
        assert "=== EXTRACTED FIELDS ===" in content
        assert "=== RAW PANEL TEXT ===" in content

    def test_missing_extracted_fields_still_saves(self, mock_pipeline, client, extractions_dir):
        payload = {
            "url": "https://www.linkedin.com/jobs/view/999/",
            "extracted": {},
            "rawPanelText": "Some raw text",
            "timestamp": "2026-04-08T12-00-00",
        }
        resp = client.post("/api/extension/extract", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "999" in data["filename"]
        files = list(extractions_dir.iterdir())
        assert len(files) == 1

    def test_missing_url_returns_422(self, mock_pipeline, client):
        payload = {
            "extracted": {},
            "rawPanelText": "text",
            "timestamp": "2026-04-08T12-00-00",
        }
        resp = client.post("/api/extension/extract", json=payload)
        assert resp.status_code == 422

    def test_missing_raw_panel_text_returns_422(self, mock_pipeline, client):
        payload = {
            "url": "https://www.linkedin.com/jobs/view/123/",
            "extracted": {},
            "timestamp": "2026-04-08T12-00-00",
        }
        resp = client.post("/api/extension/extract", json=payload)
        assert resp.status_code == 422

    def test_long_description_is_truncated(self, mock_pipeline, client, extractions_dir):
        long_desc = "A" * 250
        payload = {
            "url": "https://www.linkedin.com/jobs/view/777/",
            "extracted": {
                "title": "Data Engineer",
                "description": long_desc,
            },
            "rawPanelText": "raw text",
            "timestamp": "2026-04-08T13-00-00",
        }
        resp = client.post("/api/extension/extract", json=payload)
        assert resp.status_code == 200
        files = list(extractions_dir.iterdir())
        assert len(files) == 1
        content = files[0].read_text()
        assert "..." in content
        assert long_desc not in content

    def test_pipeline_success_returns_job_id(self, mock_pipeline, client, extractions_dir):
        mock_pipeline.return_value = {"job_id": 42, "error": None}
        resp = client.post("/api/extension/extract", json=RAW_EXTRACTION_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["job_id"] == 42
        assert data["filename"].endswith(".txt")
        files = list(extractions_dir.iterdir())
        assert len(files) == 1

    def test_pipeline_failure_still_saves_txt(self, mock_pipeline, client, extractions_dir):
        mock_pipeline.return_value = {"job_id": None, "error": "title is required"}
        resp = client.post("/api/extension/extract", json=RAW_EXTRACTION_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["job_id"] is None
        assert data["extraction_error"] == "title is required"
        files = list(extractions_dir.iterdir())
        assert len(files) == 1

    def test_pipeline_exception_still_saves_txt(self, mock_pipeline, client, extractions_dir):
        mock_pipeline.side_effect = Exception("LLM exploded")
        resp = client.post("/api/extension/extract", json=RAW_EXTRACTION_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["job_id"] is None
        assert "LLM exploded" in data["extraction_error"]
        files = list(extractions_dir.iterdir())
        assert len(files) == 1

    def test_duplicate_url_skips_pipeline(self, mock_pipeline, client, extractions_dir):
        with patch("src.api.extension_routes.httpx.AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = [{"id": 42, "title": "Existing Job"}]
            mock_resp.raise_for_status.return_value = None

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            resp = client.post("/api/extension/extract", json=VALID_PAYLOAD)
            assert resp.status_code == 200
            data = resp.json()
            assert data["duplicate"] is True
            assert data["existing_job_id"] == 42
            assert data["message"] == "Already saved"
            assert data["filename"].endswith(".txt")
            mock_pipeline.assert_not_called()

    def test_no_duplicate_runs_pipeline(self, mock_pipeline, client, extractions_dir):
        with patch("src.api.extension_routes.httpx.AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = []
            mock_resp.raise_for_status.return_value = None

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            resp = client.post("/api/extension/extract", json=VALID_PAYLOAD)
            assert resp.status_code == 200
            data = resp.json()
            assert "duplicate" not in data
            mock_pipeline.assert_called_once()
