"""Tests for query_resume_corpus, in particular its timeout boundary.

Before the timeout was added, a SIGSTOP'd chroma process would accept TCP
connections but never reply, so the resume pipeline hung forever inside the
rag_retrieval step with no error and no progress. The timeout turns that
silent hang into a visible TimeoutError surfaced through LangGraph.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.memory import rag


@pytest.mark.asyncio
async def test_query_returns_empty_when_no_active_collection():
    with patch("src.memory.rag.active_collection", new=AsyncMock(return_value=None)):
        result = await rag.query_resume_corpus("python")
    assert result == []


@pytest.mark.asyncio
async def test_query_formats_chunks_from_chroma_results():
    fake_col = MagicMock()
    fake_col.query = AsyncMock(return_value={
        "documents": [["ignored doc text"]],
        "metadatas": [[{
            "raw_text": "built a distributed queue",
            "resume_name": "A.pdf",
            "section_type": "experience",
        }]],
        "distances": [[0.42]],
    })
    with patch("src.memory.rag.active_collection", new=AsyncMock(return_value=fake_col)):
        result = await rag.query_resume_corpus("queues")

    assert result == [{
        "text": "built a distributed queue",
        "resume_name": "A.pdf",
        "section_type": "experience",
        "distance": 0.42,
    }]


@pytest.mark.asyncio
async def test_query_raises_timeout_when_chroma_hangs(monkeypatch, caplog):
    """A wedged chroma (stopped process, network black hole) must raise
    TimeoutError within the configured deadline instead of hanging the
    resume pipeline indefinitely."""
    monkeypatch.setattr(rag, "QUERY_TIMEOUT_SECONDS", 0.1)

    hanging_col = MagicMock()

    async def _never_returns(*_args, **_kwargs):
        await asyncio.sleep(10)  # much longer than the timeout
        return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    hanging_col.query = _never_returns

    with patch("src.memory.rag.active_collection", new=AsyncMock(return_value=hanging_col)):
        with caplog.at_level("ERROR", logger="jobtracker.rag"):
            start = asyncio.get_event_loop().time()
            with pytest.raises(TimeoutError):
                await rag.query_resume_corpus("anything")
            elapsed = asyncio.get_event_loop().time() - start

    # Deadline is 0.1s; should raise well before the 10s sleep would have finished.
    assert elapsed < 2.0, f"wait_for took {elapsed}s, deadline should have fired"
    assert any("timed out" in r.message for r in caplog.records), \
        "expected a 'timed out' log line on the jobtracker.rag logger"
