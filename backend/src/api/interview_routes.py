import asyncio
import logging
import os

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.agents.interview_db import (
    create_session, load_session, update_session_status,
    load_turns, load_results, list_sessions_for_job, delete_session,
    try_transition_to_scoring,
)
from src.agents.interview_engine import run_planning, run_scoring
from src.auth.credentials import load_credential

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/interview")

_background_tasks: set[asyncio.Task] = set()


class StartRequest(BaseModel):
    job_id: int
    resume_id: int | None = None
    interview_type: str
    difficulty: str
    duration_minutes: int
    voice: str = "nova"
    focus_area: str | None = None


@router.post("/start")
async def start_interview(req: StartRequest):
    # Validate OpenAI credentials for STT/TTS
    openai_cred = await load_credential("openai")
    if not openai_cred:
        raise HTTPException(
            status_code=400,
            detail="OpenAI API key required for speech-to-text and text-to-speech. Add one in Settings > API Keys.",
        )

    try:
        session_id = await create_session(
            job_id=req.job_id,
            resume_id=req.resume_id,
            interview_type=req.interview_type,
            difficulty=req.difficulty,
            duration_minutes=req.duration_minutes,
            voice=req.voice,
            focus_area=req.focus_area,
        )
    except Exception as exc:
        if "FOREIGN KEY constraint failed" in str(exc):
            raise HTTPException(status_code=400, detail="Invalid job_id or resume_id")
        raise

    async def _do_planning():
        try:
            await run_planning(session_id)
        except Exception as exc:
            logger.exception("Planning failed for session %s: %s", session_id, exc)
            await update_session_status(session_id, "interrupted")

    task = asyncio.create_task(_do_planning())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    host = os.environ.get("INTERVIEW_WS_HOST", "localhost")
    port = os.environ.get("INTERVIEW_WS_PORT", "8000")
    ws_url = f"ws://{host}:{port}/ws/interview/{session_id}"

    return {"session_id": session_id, "ws_url": ws_url, "status": "planning"}


@router.patch("/{session_id}/end")
async def end_interview(session_id: int):
    session = await load_session(session_id)
    if session["status"] in ("scoring", "completed"):
        return {"status": session["status"]}

    if not await try_transition_to_scoring(session_id):
        return {"status": (await load_session(session_id))["status"]}

    async def _do_scoring():
        try:
            await run_scoring(session_id)
        except Exception as exc:
            logger.exception("Scoring failed for session %s: %s", session_id, exc)
            await update_session_status(session_id, "interrupted")

    task = asyncio.create_task(_do_scoring())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {"status": "scoring"}


@router.patch("/{session_id}/pause")
async def pause_interview(session_id: int):
    session = await load_session(session_id)
    if session["status"] != "active":
        raise HTTPException(status_code=400, detail="Can only pause active sessions")
    await update_session_status(session_id, "paused")
    return {"status": "paused"}


@router.patch("/{session_id}/resume")
async def resume_interview(session_id: int):
    session = await load_session(session_id)
    if session["status"] != "paused":
        raise HTTPException(status_code=400, detail="Can only resume paused sessions")
    await update_session_status(session_id, "active")
    return {"status": "active"}


@router.get("/sessions")
async def list_sessions(job_id: int = Query(...)):
    return await list_sessions_for_job(job_id)


@router.get("/{session_id}")
async def get_session(session_id: int):
    session = await load_session(session_id)
    turns = await load_turns(session_id)
    results = await load_results(session_id)
    return {"session": session, "turns": turns, "results": results}


@router.delete("/{session_id}")
async def delete_interview(session_id: int):
    await delete_session(session_id)
    return {"ok": True}
