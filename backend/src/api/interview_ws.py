import asyncio
import json
import logging
import time
from dataclasses import dataclass, field

from fastapi import WebSocket, WebSocketDisconnect

from src.agents.interview_db import load_session, load_turns
from src.agents.audio_pipeline import process_audio_turn, synthesize_speech

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 15
HEARTBEAT_TIMEOUT = 45
MAX_TURNS_PER_SESSION = 60
MIN_AUDIO_INTERVAL = 2.0


@dataclass
class ConnectionState:
    session_id: int
    connected_at: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)
    is_processing: bool = False
    current_task: asyncio.Task | None = None
    last_audio_time: float = 0.0


async def interview_ws_handler(websocket: WebSocket, session_id: int):
    await websocket.accept()

    # Validate session
    try:
        session = load_session(session_id)
    except ValueError:
        await websocket.send_json({"type": "error", "code": "session_not_found", "message": "Session not found"})
        await websocket.close()
        return

    if session["status"] not in ("active", "paused", "planning"):
        await websocket.send_json({
            "type": "error", "code": "session_expired",
            "message": f"Session is {session['status']}, cannot connect",
        })
        await websocket.close()
        return

    state = ConnectionState(session_id=session_id)
    turns = load_turns(session_id)

    await websocket.send_json({
        "type": "connected",
        "session_id": session_id,
        "status": session["status"],
        "turn_count": len(turns),
    })

    # Start heartbeat task
    heartbeat_task = asyncio.create_task(_heartbeat_loop(websocket, state))

    try:
        while True:
            message = await websocket.receive()

            if message.get("type") == "websocket.disconnect":
                break

            # Handle binary (audio)
            if "bytes" in message and message["bytes"]:
                await _handle_audio(websocket, state, message["bytes"], session["voice"])
                continue

            # Handle JSON text messages
            if "text" in message and message["text"]:
                try:
                    data = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")

                if msg_type == "ping":
                    state.last_ping = time.time()
                    await websocket.send_json({"type": "pong"})

                elif msg_type == "text":
                    # Text fallback — treat as if it were audio transcript
                    await _handle_text_input(websocket, state, data.get("content", ""), session["voice"])

                elif msg_type == "end_interview":
                    await websocket.send_json({"type": "interview_ending"})
                    break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session %s", session_id)
    except Exception as exc:
        logger.exception("WebSocket error for session %s: %s", session_id, exc)
    finally:
        heartbeat_task.cancel()
        if state.current_task:
            state.current_task.cancel()


async def _handle_audio(websocket: WebSocket, state: ConnectionState, audio_bytes: bytes, voice: str):
    # Rate limiting
    now = time.time()
    if now - state.last_audio_time < MIN_AUDIO_INTERVAL:
        await websocket.send_json({"type": "error", "code": "rate_limited", "message": "Too fast, wait a moment"})
        return

    # Backpressure
    if state.is_processing:
        await websocket.send_json({"type": "error", "code": "busy", "message": "Still processing previous answer"})
        return

    # Turn limit
    turns = load_turns(state.session_id)
    if len(turns) >= MAX_TURNS_PER_SESSION:
        await websocket.send_json({"type": "error", "code": "turn_limit", "message": "Maximum turns reached"})
        return

    state.is_processing = True
    state.last_audio_time = now

    try:
        turn_response, transcript = await process_audio_turn(state.session_id, audio_bytes, voice)

        # Send transcript back to client
        if transcript:
            await websocket.send_json({"type": "transcript", "text": transcript})

        # Send interviewer text
        await websocket.send_json({
            "type": "interviewer_text", "delta": turn_response.interviewer_message, "done": True,
        })

        # Stream TTS audio (graceful degradation if TTS unavailable)
        try:
            await websocket.send_json({"type": "audio_start"})
            async for chunk in synthesize_speech(turn_response.interviewer_message, voice):
                await websocket.send_bytes(chunk)
            await websocket.send_json({"type": "audio_end"})
        except Exception as tts_exc:
            logger.warning("TTS failed, text-only fallback: %s", tts_exc)
            await websocket.send_json({"type": "audio_end"})

    except asyncio.TimeoutError:
        await websocket.send_json({"type": "error", "code": "timeout", "message": "Processing timed out"})
    except Exception as exc:
        logger.exception("Turn processing failed: %s", exc)
        await websocket.send_json({"type": "error", "code": "processing_failed", "message": str(exc)[:200]})
    finally:
        state.is_processing = False


async def _handle_text_input(websocket: WebSocket, state: ConnectionState, text: str, voice: str):
    """Handle text fallback — same flow as audio but skip STT."""
    if not text.strip():
        return

    if state.is_processing:
        await websocket.send_json({"type": "error", "code": "busy", "message": "Still processing"})
        return

    turns = load_turns(state.session_id)
    if len(turns) >= MAX_TURNS_PER_SESSION:
        await websocket.send_json({"type": "error", "code": "turn_limit", "message": "Maximum turns reached"})
        return

    state.is_processing = True

    try:
        from src.agents.interview_engine import process_interview_turn

        loop = asyncio.get_event_loop()
        turn_response = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: process_interview_turn(state.session_id, text)),
            timeout=30.0,
        )

        await websocket.send_json({
            "type": "interviewer_text", "delta": turn_response.interviewer_message, "done": True,
        })

        # TTS with graceful degradation
        try:
            await websocket.send_json({"type": "audio_start"})
            async for chunk in synthesize_speech(turn_response.interviewer_message, voice):
                await websocket.send_bytes(chunk)
            await websocket.send_json({"type": "audio_end"})
        except Exception as tts_exc:
            logger.warning("TTS failed, text-only fallback: %s", tts_exc)
            await websocket.send_json({"type": "audio_end"})

    except asyncio.TimeoutError:
        await websocket.send_json({"type": "error", "code": "timeout", "message": "Processing timed out"})
    except Exception as exc:
        logger.exception("Text turn failed: %s", exc)
        await websocket.send_json({"type": "error", "code": "processing_failed", "message": str(exc)[:200]})
    finally:
        state.is_processing = False


async def _heartbeat_loop(websocket: WebSocket, state: ConnectionState):
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            if time.time() - state.last_ping > HEARTBEAT_TIMEOUT:
                logger.info("Heartbeat timeout for session %s", state.session_id)
                await websocket.close(code=1000, reason="heartbeat_timeout")
                break
    except asyncio.CancelledError:
        pass
