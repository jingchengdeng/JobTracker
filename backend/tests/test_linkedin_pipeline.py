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
