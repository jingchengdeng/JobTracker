from unittest.mock import patch, MagicMock, AsyncMock


def _make_valid_extraction(**overrides):
    base = {
        "title": "Software Engineer",
        "company": "Acme Corp",
        "location": "San Francisco, CA",
        "description": "Build and maintain backend services.",
        "salary_min": 130000,
        "salary_max": 170000,
        "salary_currency": "USD",
        "job_type": "full_time",
        "work_mode": "remote",
    }
    base.update(overrides)
    return base


def _make_state(**overrides):
    base = {
        "raw_text": "Raw job posting text here.",
        "url": "https://www.linkedin.com/jobs/view/123",
        "extracted": None,
        "validation_errors": [],
        "retry_count": 0,
        "job_id": None,
        "error": None,
    }
    base.update(overrides)
    return base


class TestExtractFieldsNode:
    @patch("src.agents.extraction_pipeline.get_linkedin_model")
    async def test_extracts_structured_output(self, mock_get_model):
        from src.agents.extraction_pipeline import extract_fields

        mock_llm = MagicMock()
        mock_get_model.return_value = mock_llm

        extraction_data = _make_valid_extraction()
        mock_result = MagicMock()
        mock_result.model_dump.return_value = extraction_data

        structured_mock = MagicMock()
        structured_mock.ainvoke = AsyncMock(return_value=mock_result)
        mock_llm.with_structured_output.return_value = structured_mock

        state = _make_state()
        result = await extract_fields(state)

        assert result["extracted"] == extraction_data
        assert result["retry_count"] == 0

    @patch("src.agents.extraction_pipeline.get_linkedin_model")
    async def test_retry_includes_validation_errors_in_prompt(self, mock_get_model):
        from src.agents.extraction_pipeline import extract_fields
        from langchain_core.messages import HumanMessage

        mock_llm = MagicMock()
        mock_get_model.return_value = mock_llm

        extraction_data = _make_valid_extraction()
        mock_result = MagicMock()
        mock_result.model_dump.return_value = extraction_data

        structured_mock = MagicMock()
        structured_mock.ainvoke = AsyncMock(return_value=mock_result)
        mock_llm.with_structured_output.return_value = structured_mock

        errors = ["salary_min (200000) must be <= salary_max (150000)"]
        state = _make_state(validation_errors=errors, retry_count=0)
        result = await extract_fields(state)

        call_args = structured_mock.ainvoke.call_args[0][0]
        human_msg = next(m for m in call_args if isinstance(m, HumanMessage))
        assert "salary_min" in human_msg.content
        assert result["retry_count"] == 1


class TestValidateFieldsNode:
    async def test_valid_extraction_passes(self):
        from src.agents.extraction_pipeline import validate_fields

        state = _make_state(extracted=_make_valid_extraction())
        result = await validate_fields(state)

        assert result["validation_errors"] == []

    async def test_invalid_extraction_returns_errors(self):
        from src.agents.extraction_pipeline import validate_fields

        bad_data = _make_valid_extraction(salary_min=200000, salary_max=150000)
        state = _make_state(extracted=bad_data)
        result = await validate_fields(state)

        assert len(result["validation_errors"]) > 0
        assert any("salary_min" in e for e in result["validation_errors"])


class TestInsertJobNode:
    @patch("src.agents.extraction_pipeline.httpx.AsyncClient")
    async def test_successful_insert(self, mock_client_cls):
        from src.agents.extraction_pipeline import insert_job

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 42}
        mock_response.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        state = _make_state(extracted=_make_valid_extraction())
        result = await insert_job(state)

        assert result["job_id"] == 42
        assert result["error"] is None

        call_kwargs = mock_client.post.call_args
        body = call_kwargs[1]["json"]
        assert body["source"] == "linkedin"
        assert body["title"] == "Software Engineer"

    @patch("src.agents.extraction_pipeline.httpx.AsyncClient")
    async def test_insert_failure_sets_error(self, mock_client_cls):
        from src.agents.extraction_pipeline import insert_job

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        state = _make_state(extracted=_make_valid_extraction())
        result = await insert_job(state)

        assert result["job_id"] is None
        assert result["error"] is not None
        assert "Connection refused" in result["error"]


class TestRunExtractionPipeline:
    @patch("src.agents.extraction_pipeline.httpx.AsyncClient")
    @patch("src.agents.extraction_pipeline.get_linkedin_model")
    async def test_full_pipeline_success(self, mock_get_model, mock_client_cls):
        from src.agents.extraction_pipeline import run_extraction_pipeline

        mock_llm = MagicMock()
        mock_get_model.return_value = mock_llm

        extraction_data = _make_valid_extraction()
        mock_result = MagicMock()
        mock_result.model_dump.return_value = extraction_data

        structured_mock = MagicMock()
        structured_mock.ainvoke = AsyncMock(return_value=mock_result)
        mock_llm.with_structured_output.return_value = structured_mock

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 99}
        mock_response.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await run_extraction_pipeline(
            raw_text="Some linkedin job text",
            url="https://www.linkedin.com/jobs/view/999",
        )

        assert result["job_id"] == 99
        assert result["error"] is None

    @patch("src.agents.extraction_pipeline.get_linkedin_model")
    async def test_pipeline_returns_error_on_llm_failure(self, mock_get_model):
        from src.agents.extraction_pipeline import run_extraction_pipeline

        mock_get_model.side_effect = ValueError("No credentials configured")

        result = await run_extraction_pipeline(
            raw_text="Some linkedin job text",
            url="https://www.linkedin.com/jobs/view/999",
        )

        assert result["job_id"] is None
        assert result["error"] is not None
        assert "No credentials configured" in result["error"]
