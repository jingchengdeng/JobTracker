import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock


class TestPreconditionCheck:
    async def test_full_pipeline_when_description_exists(self):
        from src.agents.linkedin_pipeline import precondition_check
        job = {"title": "SWE", "company": "Stripe", "description": "Build payment APIs..."}
        result = await precondition_check(job)
        assert result["mode"] == "full"

    async def test_full_pipeline_when_only_title_exists(self):
        from src.agents.linkedin_pipeline import precondition_check
        job = {"title": "Senior Engineer", "company": "Stripe", "description": None}
        result = await precondition_check(job)
        assert result["mode"] == "full"

    async def test_basic_pipeline_when_only_company(self):
        from src.agents.linkedin_pipeline import precondition_check
        job = {"title": "", "company": "Stripe", "description": None}
        result = await precondition_check(job)
        assert result["mode"] == "basic"


class TestBuildSearchQueries:
    async def test_full_mode_generates_five_queries(self):
        from src.agents.linkedin_pipeline import build_search_queries
        analysis = {
            "role_title": "Senior Software Engineer",
            "role_domain": "engineering",
            "seniority": "senior",
            "leadership_titles": ["Engineering Manager", "Director of Engineering"],
            "department_keywords": ["backend"],
        }
        queries = await build_search_queries("Stripe", analysis)
        assert len(queries) == 5
        assert all("site:linkedin.com/in" in q["query"] for q in queries)
        assert any("recruiter" in q["query"].lower() for q in queries)
        assert any('"talent acquisition"' in q["query"].lower() for q in queries)
        assert any('"Engineering Manager"' in q["query"] for q in queries)

    async def test_basic_mode_generates_four_queries(self):
        from src.agents.linkedin_pipeline import build_search_queries
        queries = await build_search_queries("Stripe", None)
        assert len(queries) == 4
        assert all("site:linkedin.com/in" in q["query"] for q in queries)
        assert all(q["tag"] in ("recruiter", "ta", "hiring_mgr", "hr") for q in queries)


class TestMergeAndDeduplicate:
    async def test_deduplicates_by_url(self):
        from src.agents.linkedin_pipeline import merge_and_deduplicate
        results = {
            "recruiter": [
                {"name": "Amy", "title": "Recruiter", "location": "Miami", "linkedin_url": "https://www.linkedin.com/in/amy"},
            ],
            "ta": [
                {"name": "Amy", "title": "Talent Acquisition", "location": "Miami", "linkedin_url": "https://www.linkedin.com/in/amy"},
            ],
        }
        merged = await merge_and_deduplicate(results)
        assert len(merged) == 1
        assert "recruiter" in merged[0]["source_query"]
        assert "ta" in merged[0]["source_query"]

    async def test_keeps_unique_entries(self):
        from src.agents.linkedin_pipeline import merge_and_deduplicate
        results = {
            "recruiter": [
                {"name": "Amy", "title": "Recruiter", "location": None, "linkedin_url": "https://www.linkedin.com/in/amy"},
            ],
            "hr": [
                {"name": "Bob", "title": "HR", "location": None, "linkedin_url": "https://www.linkedin.com/in/bob"},
            ],
        }
        merged = await merge_and_deduplicate(results)
        assert len(merged) == 2


class TestFilterAndRank:
    async def test_filters_below_threshold(self):
        from src.agents.linkedin_pipeline import filter_and_rank
        people = [
            {"linkedin_url": "a", "relevance_score": 80},
            {"linkedin_url": "b", "relevance_score": 30},
            {"linkedin_url": "c", "relevance_score": 60},
        ]
        filtered = await filter_and_rank(people)
        assert len(filtered) == 2
        assert filtered[0]["relevance_score"] == 80
        assert all(p.get("low_confidence") == 0 for p in filtered)

    async def test_returns_top3_with_low_confidence_when_all_below_threshold(self):
        from src.agents.linkedin_pipeline import filter_and_rank
        people = [
            {"linkedin_url": "a", "relevance_score": 30},
            {"linkedin_url": "b", "relevance_score": 20},
            {"linkedin_url": "c", "relevance_score": 35},
            {"linkedin_url": "d", "relevance_score": 10},
        ]
        filtered = await filter_and_rank(people)
        assert len(filtered) == 3
        assert filtered[0]["relevance_score"] == 35
        assert all(p["low_confidence"] == 1 for p in filtered)

    async def test_caps_at_ten(self):
        from src.agents.linkedin_pipeline import filter_and_rank
        people = [{"linkedin_url": str(i), "relevance_score": 50 + i} for i in range(15)]
        filtered = await filter_and_rank(people)
        assert len(filtered) == 10


class TestTruncateNote:
    async def test_short_note_unchanged(self):
        from src.agents.linkedin_pipeline import truncate_note
        assert await truncate_note("Hi Amy, great to connect!") == "Hi Amy, great to connect!"

    async def test_long_note_truncated_at_word_boundary(self):
        from src.agents.linkedin_pipeline import truncate_note
        long_note = "word " * 100  # 500 chars
        result = await truncate_note(long_note)
        assert len(result) <= 300
        assert not result.endswith(" ")

    async def test_exactly_300_chars_unchanged(self):
        from src.agents.linkedin_pipeline import truncate_note
        note = "x" * 300
        assert len(await truncate_note(note)) == 300


class TestRunLinkedinPipelineIntegration:
    """Integration test: run_linkedin_pipeline delegates to linkedin_graph.ainvoke."""

    @patch("src.agents.linkedin_graph.linkedin_graph")
    @pytest.mark.asyncio
    async def test_full_pipeline_completes(self, mock_graph):
        from src.agents.linkedin_pipeline import run_linkedin_pipeline

        mock_graph.ainvoke = AsyncMock(return_value={})

        await run_linkedin_pipeline(search_id=42, job_id=1, workflow_run_id="test-wf-id")

        mock_graph.ainvoke.assert_called_once()
        call_args = mock_graph.ainvoke.call_args[0][0]
        assert call_args["search_id"] == 42
        assert call_args["job_id"] == 1
        assert call_args["workflow_run_id"] == "test-wf-id"

    @patch("src.agents.linkedin_graph.linkedin_graph")
    @pytest.mark.asyncio
    async def test_generates_workflow_run_id_when_none(self, mock_graph):
        from src.agents.linkedin_pipeline import run_linkedin_pipeline

        mock_graph.ainvoke = AsyncMock(return_value={})

        await run_linkedin_pipeline(search_id=7, job_id=2)

        call_args = mock_graph.ainvoke.call_args[0][0]
        assert call_args["workflow_run_id"] is not None
        assert len(call_args["workflow_run_id"]) == 36  # UUID format
