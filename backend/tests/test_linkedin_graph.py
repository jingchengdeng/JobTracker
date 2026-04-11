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
