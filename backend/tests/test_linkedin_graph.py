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
