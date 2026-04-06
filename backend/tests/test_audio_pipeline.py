import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

from tests.test_interview_db import _create_tables
from src.agents.interview_schemas import TurnResponse


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    _create_tables(db_path)
    monkeypatch.setenv("JOBTRACKER_DB_PATH", db_path)
    return db_path


@pytest.fixture
def session_with_plan(test_db):
    """Create a session with a plan so turn processing works."""
    from src.agents.interview_db import create_session, save_plan, save_turn, update_session_status

    session_id = create_session(
        job_id=1, resume_id=1, interview_type="technical",
        difficulty="medium", duration_minutes=30, voice="nova",
    )
    save_plan(session_id, {
        "topics": [{"id": "t1", "area": "Design", "questions": ["Q1"], "rubric": ["R1"], "time_allocation_minutes": 10}],
        "total_questions_target": 3,
        "opening_prompt": "Hello",
    }, [{"name": "Depth", "weight": 0.5, "description": "d"}])
    save_turn(session_id, "interviewer", "Hello")
    update_session_status(session_id, "active")
    return session_id


class TestSTT:
    @pytest.mark.asyncio
    @patch("src.agents.audio_pipeline._get_openai_client")
    async def test_transcribe_returns_text(self, mock_client_fn):
        from src.agents.audio_pipeline import transcribe_audio

        mock_client = AsyncMock()
        mock_client.audio.transcriptions.create.return_value = MagicMock(text="Hello world")
        mock_client_fn.return_value = mock_client

        result = await transcribe_audio(b"fake-audio-bytes")
        assert result == "Hello world"

    @pytest.mark.asyncio
    @patch("src.agents.audio_pipeline._get_openai_client")
    async def test_transcribe_empty_returns_none(self, mock_client_fn):
        from src.agents.audio_pipeline import transcribe_audio

        mock_client = AsyncMock()
        mock_client.audio.transcriptions.create.return_value = MagicMock(text="")
        mock_client_fn.return_value = mock_client

        result = await transcribe_audio(b"fake-audio-bytes")
        assert result is None


class TestTTS:
    @pytest.mark.asyncio
    @patch("src.agents.audio_pipeline._get_openai_client")
    async def test_synthesize_yields_chunks(self, mock_client_fn):
        from src.agents.audio_pipeline import synthesize_speech

        mock_response = AsyncMock()
        mock_response.iter_bytes = lambda chunk_size: _async_iter([b"chunk1", b"chunk2"])
        mock_client = AsyncMock()
        mock_client.audio.speech.create.return_value = mock_response
        mock_client_fn.return_value = mock_client

        chunks = []
        async for chunk in synthesize_speech("Hello there.", "nova"):
            chunks.append(chunk)

        assert len(chunks) == 2
        assert chunks[0] == b"chunk1"


async def _async_iter(items):
    for item in items:
        yield item
