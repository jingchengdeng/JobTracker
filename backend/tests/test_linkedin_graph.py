"""Tests for the refactored LinkedIn graph: reducer, factories, structure,
lane-skip routing, parallel timing, shared browser."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSearchResultsReducer:
    def test_merges_disjoint_keys(self):
        from src.agents.linkedin_graph import _merge_results
        a = {"recruiter": [{"name": "Amy"}]}
        b = {"ta": [{"name": "Bob"}]}
        merged = _merge_results(a, b)
        assert merged == {"recruiter": [{"name": "Amy"}], "ta": [{"name": "Bob"}]}

    def test_later_wins_on_key_collision(self):
        from src.agents.linkedin_graph import _merge_results
        a = {"leadership": [{"name": "old"}]}
        b = {"leadership": [{"name": "new"}]}
        merged = _merge_results(a, b)
        assert merged == {"leadership": [{"name": "new"}]}

    def test_none_operand_is_treated_as_empty(self):
        from src.agents.linkedin_graph import _merge_results
        assert _merge_results(None, {"recruiter": []}) == {"recruiter": []}
        assert _merge_results({"recruiter": []}, None) == {"recruiter": []}


class TestBraveSearchFactory:
    @pytest.mark.asyncio
    async def test_returns_single_key_dict_on_success(self):
        from src.agents import linkedin_graph
        node = linkedin_graph.make_brave_search_node("recruiter")
        state = {
            "workflow_run_id": "test-wf",
            "job_id": 1,
            "brave_key": "k",
            "queries": [{"query": "q1", "tag": "recruiter"}],
        }
        fake_people = [{"name": "Amy", "linkedin_url": "https://www.linkedin.com/in/amy"}]
        with patch.object(
            linkedin_graph, "brave_search_profiles", AsyncMock(return_value=fake_people)
        ):
            result = await node(state)
        assert result == {"search_results": {"recruiter": fake_people}}

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_brave_key(self):
        from src.agents import linkedin_graph
        node = linkedin_graph.make_brave_search_node("ta")
        state = {
            "workflow_run_id": "test-wf",
            "job_id": 1,
            "queries": [{"query": "q1", "tag": "ta"}],
        }
        result = await node(state)
        assert result == {}

    @pytest.mark.asyncio
    async def test_fails_open_on_exception(self):
        from src.agents import linkedin_graph
        node = linkedin_graph.make_brave_search_node("hr")
        state = {
            "workflow_run_id": "test-wf",
            "job_id": 1,
            "brave_key": "k",
            "queries": [{"query": "q1", "tag": "hr"}],
        }
        with patch.object(
            linkedin_graph, "brave_search_profiles", AsyncMock(side_effect=RuntimeError("boom"))
        ):
            result = await node(state)
        assert result == {"search_results": {"hr": []}}


class TestBrowserSearchFactory:
    @pytest.mark.asyncio
    async def test_returns_single_key_dict_on_success(self):
        from src.agents import linkedin_graph
        node = linkedin_graph.make_browser_search_node("hiring_mgr")
        fake_browser = object()
        state = {
            "workflow_run_id": "test-wf",
            "job_id": 1,
            "browser": fake_browser,
            "queries": [{"query": "q1", "tag": "hiring_mgr"}],
        }
        fake_people = [{"name": "Cara", "linkedin_url": "https://www.linkedin.com/in/cara"}]
        with patch.object(
            linkedin_graph, "run_google_search", AsyncMock(return_value=fake_people)
        ):
            result = await node(state)
        assert result == {"search_results": {"hiring_mgr": fake_people}}

    @pytest.mark.asyncio
    async def test_returns_empty_when_browser_missing(self):
        from src.agents import linkedin_graph
        node = linkedin_graph.make_browser_search_node("leadership")
        state = {
            "workflow_run_id": "test-wf",
            "job_id": 1,
            "queries": [{"query": "q1", "tag": "leadership"}],
        }
        result = await node(state)
        assert result == {}


class TestLaunchBrowserNode:
    @pytest.mark.asyncio
    async def test_skips_if_browser_already_launched(self):
        from src.agents import linkedin_graph
        fake_browser = object()
        state = {
            "workflow_run_id": "test-wf",
            "job_id": 1,
            "browser": fake_browser,
        }
        result = await linkedin_graph.launch_browser_node(state)
        assert result == {}

    @pytest.mark.asyncio
    async def test_launches_once_when_missing(self):
        from src.agents import linkedin_graph
        fake_pw = MagicMock()
        fake_pw.start = AsyncMock(return_value=fake_pw)
        fake_browser = MagicMock()
        with patch.object(
            linkedin_graph, "async_playwright", return_value=fake_pw
        ), patch.object(
            linkedin_graph, "launch_stealth_browser",
            AsyncMock(return_value=(fake_browser, None)),
        ):
            result = await linkedin_graph.launch_browser_node({
                "workflow_run_id": "test-wf", "job_id": 1,
            })
        assert result["browser"] is fake_browser
        assert result["_display"] is None
        assert result["_playwright"] is fake_pw


class TestCloseBrowserNode:
    @pytest.mark.asyncio
    async def test_closes_and_clears_handles(self):
        from src.agents import linkedin_graph
        fake_browser = MagicMock()
        fake_browser.close = AsyncMock()
        fake_display = MagicMock()
        fake_pw = MagicMock()
        fake_pw.stop = AsyncMock()
        result = await linkedin_graph.close_browser_node({
            "workflow_run_id": "test-wf", "job_id": 1,
            "browser": fake_browser, "_display": fake_display, "_playwright": fake_pw,
        })
        fake_browser.close.assert_awaited_once()
        fake_display.stop.assert_called_once()
        fake_pw.stop.assert_awaited_once()
        assert result == {"browser": None, "_display": None, "_playwright": None}

    @pytest.mark.asyncio
    async def test_tolerates_missing_browser(self):
        from src.agents import linkedin_graph
        result = await linkedin_graph.close_browser_node({
            "workflow_run_id": "test-wf", "job_id": 1,
        })
        assert result == {"browser": None, "_display": None, "_playwright": None}


class TestAnalyzeJdNode:
    @pytest.mark.asyncio
    async def test_writes_both_analysis_and_domain(self):
        from src.agents import linkedin_graph
        fake = {
            "role_title": "SWE", "role_domain": "engineering", "seniority": "senior",
            "leadership_titles": [], "department_keywords": [], "domain": "stripe.com",
        }
        with patch.object(linkedin_graph, "run_analyze_jd", AsyncMock(return_value=fake)):
            result = await linkedin_graph.analyze_jd_node({
                "workflow_run_id": "test-wf", "job_id": 1,
                "job": {"title": "SWE", "description": "..."},
            })
        assert result["analysis"]["role_title"] == "SWE"
        assert result["domain"] == "stripe.com"


class TestReviewLeadershipNodes:
    @pytest.mark.asyncio
    async def test_returns_empty_when_no_retry_needed(self):
        from src.agents import linkedin_graph
        from src.agents.linkedin_schemas import LeadershipReview

        review = LeadershipReview(
            relevant_count=4, total_count=5, needs_retry=False, refined_query=None,
        )
        with patch.object(
            linkedin_graph, "run_review_leadership", AsyncMock(return_value=review)
        ):
            state = {
                "workflow_run_id": "test-wf", "job_id": 1,
                "analysis": {"role_domain": "engineering"},
                "brave_key": "k",
                "search_results": {"leadership": [{"name": "x", "title": "Eng Mgr"}]},
                "job": {"company": "Stripe"},
            }
            result = await linkedin_graph.review_leadership_brave_node(state)
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_fresh_dict_on_retry(self):
        from src.agents import linkedin_graph
        from src.agents.linkedin_schemas import LeadershipReview

        review = LeadershipReview(
            relevant_count=1, total_count=5, needs_retry=True, refined_query="head of eng",
        )
        new_people = [{"name": "y", "title": "VP Eng"}]
        with patch.object(
            linkedin_graph, "run_review_leadership", AsyncMock(return_value=review)
        ), patch.object(
            linkedin_graph, "brave_search_profiles", AsyncMock(return_value=new_people)
        ):
            original_results = {"leadership": [{"name": "x"}]}
            state = {
                "workflow_run_id": "test-wf", "job_id": 1,
                "analysis": {"role_domain": "engineering"},
                "brave_key": "k",
                "search_results": original_results,
                "job": {"company": "Stripe"},
            }
            result = await linkedin_graph.review_leadership_brave_node(state)
        assert result == {"search_results": {"leadership": new_people}}
        assert original_results == {"leadership": [{"name": "x"}]}

    @pytest.mark.asyncio
    async def test_playwright_node_shares_implementation(self):
        from src.agents import linkedin_graph
        state = {
            "workflow_run_id": "test-wf", "job_id": 1,
            "analysis": {"role_domain": "engineering"},
            "search_results": {"leadership": []},
            "job": {"company": "Stripe"},
        }
        assert await linkedin_graph.review_leadership_playwright_node(state) == {}


EXPECTED_LINKEDIN_NODES = {
    "load_job",
    "precondition_check",
    "analyze_jd",
    "load_brave_key",
    "_company_branch_entry",
    "brave_domain_search",
    "browser_domain_search",
    "enrich_company_apollo",
    "compile_summary",
    "build_queries",
    "launch_browser",
    "brave_recruiter",
    "brave_ta",
    "brave_hiring_mgr",
    "brave_hr",
    "brave_leadership",
    "browser_recruiter",
    "browser_ta",
    "browser_hiring_mgr",
    "browser_hr",
    "browser_leadership",
    "review_leadership_brave",
    "review_leadership_playwright",
    "close_browser",
    "merge_dedup",
    "score_relevance",
    "filter_rank",
    "generate_notes",
    "save_results",
}


class TestGraphStructure:
    def test_compiled_graph_has_expected_nodes(self):
        from src.agents.linkedin_graph import linkedin_graph
        compiled_nodes = set(linkedin_graph.get_graph().nodes.keys())
        compiled_nodes -= {"__start__", "__end__"}
        assert compiled_nodes == EXPECTED_LINKEDIN_NODES, (
            f"missing: {EXPECTED_LINKEDIN_NODES - compiled_nodes}, "
            f"extra: {compiled_nodes - EXPECTED_LINKEDIN_NODES}"
        )

    def test_node_count_is_29(self):
        from src.agents.linkedin_graph import linkedin_graph
        compiled_nodes = set(linkedin_graph.get_graph().nodes.keys())
        compiled_nodes -= {"__start__", "__end__"}
        assert len(compiled_nodes) == 29
