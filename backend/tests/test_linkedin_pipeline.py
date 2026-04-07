import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock


class TestPreconditionCheck:
    def test_full_pipeline_when_description_exists(self):
        from src.agents.linkedin_pipeline import precondition_check
        job = {"title": "SWE", "company": "Stripe", "description": "Build payment APIs..."}
        result = precondition_check(job)
        assert result["mode"] == "full"

    def test_full_pipeline_when_only_title_exists(self):
        from src.agents.linkedin_pipeline import precondition_check
        job = {"title": "Senior Engineer", "company": "Stripe", "description": None}
        result = precondition_check(job)
        assert result["mode"] == "full"

    def test_basic_pipeline_when_only_company(self):
        from src.agents.linkedin_pipeline import precondition_check
        job = {"title": "", "company": "Stripe", "description": None}
        result = precondition_check(job)
        assert result["mode"] == "basic"


class TestBuildSearchQueries:
    def test_full_mode_generates_five_queries(self):
        from src.agents.linkedin_pipeline import build_search_queries
        analysis = {
            "role_title": "Senior Software Engineer",
            "role_domain": "engineering",
            "seniority": "senior",
            "leadership_titles": ["Engineering Manager", "Director of Engineering"],
            "department_keywords": ["backend"],
        }
        queries = build_search_queries("Stripe", analysis)
        assert len(queries) == 5
        assert any("recruiter" in q["query"].lower() for q in queries)
        assert any("talent acquisition" in q["query"].lower() for q in queries)
        assert any("Engineering Manager" in q["query"] for q in queries)

    def test_basic_mode_generates_three_queries(self):
        from src.agents.linkedin_pipeline import build_search_queries
        queries = build_search_queries("Stripe", None)
        assert len(queries) == 3
        assert all(q["tag"] in ("recruiter", "ta", "hr") for q in queries)


class TestMergeAndDeduplicate:
    def test_deduplicates_by_url(self):
        from src.agents.linkedin_pipeline import merge_and_deduplicate
        results = {
            "recruiter": [
                {"name": "Amy", "title": "Recruiter", "location": "Miami", "linkedin_url": "https://www.linkedin.com/in/amy"},
            ],
            "ta": [
                {"name": "Amy", "title": "Talent Acquisition", "location": "Miami", "linkedin_url": "https://www.linkedin.com/in/amy"},
            ],
        }
        merged = merge_and_deduplicate(results)
        assert len(merged) == 1
        assert "recruiter" in merged[0]["source_query"]
        assert "ta" in merged[0]["source_query"]

    def test_keeps_unique_entries(self):
        from src.agents.linkedin_pipeline import merge_and_deduplicate
        results = {
            "recruiter": [
                {"name": "Amy", "title": "Recruiter", "location": None, "linkedin_url": "https://www.linkedin.com/in/amy"},
            ],
            "hr": [
                {"name": "Bob", "title": "HR", "location": None, "linkedin_url": "https://www.linkedin.com/in/bob"},
            ],
        }
        merged = merge_and_deduplicate(results)
        assert len(merged) == 2


class TestFilterAndRank:
    def test_filters_below_threshold(self):
        from src.agents.linkedin_pipeline import filter_and_rank
        people = [
            {"linkedin_url": "a", "relevance_score": 80},
            {"linkedin_url": "b", "relevance_score": 30},
            {"linkedin_url": "c", "relevance_score": 60},
        ]
        filtered = filter_and_rank(people)
        assert len(filtered) == 2
        assert filtered[0]["relevance_score"] == 80
        assert all(p.get("low_confidence") == 0 for p in filtered)

    def test_returns_top3_with_low_confidence_when_all_below_threshold(self):
        from src.agents.linkedin_pipeline import filter_and_rank
        people = [
            {"linkedin_url": "a", "relevance_score": 30},
            {"linkedin_url": "b", "relevance_score": 20},
            {"linkedin_url": "c", "relevance_score": 35},
            {"linkedin_url": "d", "relevance_score": 10},
        ]
        filtered = filter_and_rank(people)
        assert len(filtered) == 3
        assert filtered[0]["relevance_score"] == 35
        assert all(p["low_confidence"] == 1 for p in filtered)

    def test_caps_at_ten(self):
        from src.agents.linkedin_pipeline import filter_and_rank
        people = [{"linkedin_url": str(i), "relevance_score": 50 + i} for i in range(15)]
        filtered = filter_and_rank(people)
        assert len(filtered) == 10


class TestTruncateNote:
    def test_short_note_unchanged(self):
        from src.agents.linkedin_pipeline import truncate_note
        assert truncate_note("Hi Amy, great to connect!") == "Hi Amy, great to connect!"

    def test_long_note_truncated_at_word_boundary(self):
        from src.agents.linkedin_pipeline import truncate_note
        long_note = "word " * 100  # 500 chars
        result = truncate_note(long_note)
        assert len(result) <= 300
        assert not result.endswith(" ")

    def test_exactly_300_chars_unchanged(self):
        from src.agents.linkedin_pipeline import truncate_note
        note = "x" * 300
        assert len(truncate_note(note)) == 300


class TestRunLinkedinPipelineIntegration:
    """Integration test: full pipeline with mocked LLM, Playwright, and Apollo."""

    @pytest.fixture
    def db_path(self, tmp_path, monkeypatch):
        import sqlite3
        path = str(tmp_path / "test.db")
        monkeypatch.setenv("JOBTRACKER_DB_PATH", path)
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY, title TEXT, company TEXT, description TEXT)")
        conn.execute("INSERT INTO jobs (id, title, company, description) VALUES (1, 'SWE', 'Stripe', 'Build payment APIs at stripe.com. Looking for senior engineers.')")
        conn.commit()
        conn.close()
        from src.agents.linkedin_db import ensure_linkedin_tables
        ensure_linkedin_tables(path)
        return path

    @patch("src.agents.linkedin_pipeline.get_linkedin_model")
    @patch("src.agents.linkedin_pipeline.enrich_company_apollo", new_callable=AsyncMock)
    @patch("src.agents.linkedin_pipeline.run_google_search", new_callable=AsyncMock)
    @patch("src.agents.linkedin_pipeline.search_domain_google", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_full_pipeline_completes(
        self, mock_domain_search, mock_google, mock_apollo, mock_model, db_path
    ):
        from src.agents.linkedin_db import load_search, load_contacts, create_search
        from src.agents.linkedin_pipeline import run_linkedin_pipeline

        # Mock LLM
        mock_llm = MagicMock()
        mock_model.return_value = mock_llm

        # analyze_jd returns structured output
        mock_analysis = MagicMock()
        mock_analysis.model_dump.return_value = {
            "role_title": "Senior Software Engineer",
            "role_domain": "engineering",
            "seniority": "senior",
            "leadership_titles": ["Engineering Manager"],
            "department_keywords": ["backend"],
        }
        # extract_domain returns "stripe.com"
        mock_domain_response = MagicMock()
        mock_domain_response.content = "stripe.com"

        # score_relevance returns scores
        mock_scores = MagicMock()
        mock_scores.scores = [
            MagicMock(linkedin_url="https://www.linkedin.com/in/amy", score=85, reason="Recruiter"),
        ]

        # generate_notes returns notes
        mock_notes = MagicMock()
        mock_notes.notes = [
            MagicMock(linkedin_url="https://www.linkedin.com/in/amy", note="Hi Amy, I am applying for SWE at Stripe."),
        ]

        # compile_summary returns summary
        mock_summary = MagicMock()
        mock_summary.summary = "Stripe is a fintech company."

        # leadership review
        mock_review = MagicMock()
        mock_review.needs_retry = False
        mock_review.relevant_count = 1
        mock_review.total_count = 1
        mock_review.refined_query = None

        # Chain the mock calls
        structured_mock = MagicMock()
        call_count = {"n": 0}
        returns = [mock_analysis, mock_review, mock_scores, mock_notes, mock_summary]

        def invoke_side_effect(messages):
            idx = call_count["n"]
            call_count["n"] += 1
            if idx < len(returns):
                return returns[idx]
            return returns[-1]

        structured_mock.invoke = invoke_side_effect
        mock_llm.with_structured_output.return_value = structured_mock
        mock_llm.invoke.return_value = mock_domain_response

        # Mock Apollo
        mock_apollo.return_value = {"name": "Stripe", "estimated_num_employees": 8000}

        # Mock Google search results
        mock_google.return_value = [
            {"name": "Amy Salazar", "title": "Recruiter", "location": "Miami", "linkedin_url": "https://www.linkedin.com/in/amy"},
        ]
        mock_domain_search.return_value = None  # domain extracted from JD

        # Patch playwright to mock browser
        with patch("playwright.async_api.async_playwright") as mock_pw:
            mock_browser = AsyncMock()
            mock_pw.return_value.__aenter__ = AsyncMock(return_value=MagicMock(chromium=MagicMock(launch=AsyncMock(return_value=mock_browser))))
            mock_browser.close = AsyncMock()

            search_id = create_search(job_id=1)
            await run_linkedin_pipeline(search_id, 1)

        search = load_search(search_id)
        assert search["status"] == "completed"
        contacts = load_contacts(search_id)
        assert len(contacts) >= 1
