import asyncio
import io
import logging
from typing import AsyncIterator

from openai import AsyncOpenAI

from src.agents.interview_config import STT_MODEL, TTS_MODEL
from src.agents.interview_engine import process_interview_turn
from src.agents.interview_schemas import TurnResponse
from src.auth.credentials import load_api_key

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_openai_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        api_key = load_api_key("openai")
        _client = AsyncOpenAI(api_key=api_key)
    return _client


async def transcribe_audio(audio_bytes: bytes) -> str | None:
    client = _get_openai_client()
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "audio.webm"

    result = await asyncio.wait_for(
        client.audio.transcriptions.create(model=STT_MODEL, file=audio_file),
        timeout=10.0,
    )
    text = result.text.strip()
    return text if text else None


async def synthesize_speech(text: str, voice: str) -> AsyncIterator[bytes]:
    client = _get_openai_client()
    response = await asyncio.wait_for(
        client.audio.speech.create(model=TTS_MODEL, voice=voice, input=text, response_format="mp3"),
        timeout=15.0,
    )
    stream = await response.aiter_bytes(chunk_size=4096)
    async for chunk in stream:
        yield chunk


async def process_audio_turn(session_id: int, audio_bytes: bytes, voice: str) -> tuple[TurnResponse, str]:
    """Full audio turn: STT -> turn function -> returns (TurnResponse, interviewer_text).
    TTS is handled separately by the caller (WebSocket manager) so it can stream chunks."""

    # 1. STT
    transcript = await transcribe_audio(audio_bytes)
    if transcript is None:
        return TurnResponse(
            next_action="follow_up",
            current_topic_covered=False,
            next_topic_id=None,
            interviewer_message="I didn't quite catch that. Could you repeat your answer?",
        ), "I didn't quite catch that. Could you repeat your answer?"

    # 2. Turn function (now async)
    turn_response = await asyncio.wait_for(
        process_interview_turn(session_id, transcript),
        timeout=30.0,
    )

    return turn_response, transcript
