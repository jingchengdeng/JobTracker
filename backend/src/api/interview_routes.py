import asyncio
import logging
import os

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.agents.interview_db import (
    create_session, load_session, update_session_status,
    load_turns, load_results, list_sessions_for_job, delete_session,
)
from src.agents.interview_engine import run_planning, run_scoring
from src.auth.credentials import load_credential

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/interview")


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
    openai_cred = load_credential("openai")
    if not openai_cred:
        raise HTTPException(
            status_code=400,
            detail="OpenAI API key required for speech-to-text and text-to-speech. Add one in Settings > API Keys.",
        )

    session_id = create_session(
        job_id=req.job_id,
        resume_id=req.resume_id,
        interview_type=req.interview_type,
        difficulty=req.difficulty,
        duration_minutes=req.duration_minutes,
        voice=req.voice,
        focus_area=req.focus_area,
    )

    # Run planning in background thread (same pattern as resume tailor)
    def _do_planning():
        try:
            run_planning(session_id)
        except Exception as exc:
            logger.exception("Planning failed for session %s: %s", session_id, exc)
            update_session_status(session_id, "interrupted")

    asyncio.get_event_loop().run_in_executor(None, _do_planning)

    host = os.environ.get("INTERVIEW_WS_HOST", "localhost")
    port = os.environ.get("INTERVIEW_WS_PORT", "8000")
    ws_url = f"ws://{host}:{port}/ws/interview/{session_id}"

    return {"session_id": session_id, "ws_url": ws_url, "status": "planning"}


@router.patch("/{session_id}/end")
async def end_interview(session_id: int):
    session = load_session(session_id)
    # Already scoring or completed — no-op, return current status
    if session["status"] in ("scoring", "completed"):
        return {"status": session["status"]}
    if session["status"] not in ("planning", "active", "paused"):
        raise HTTPException(status_code=400, detail=f"Cannot end session in '{session['status']}' status")

    def _do_scoring():
        try:
            run_scoring(session_id)
        except Exception as exc:
            logger.exception("Scoring failed for session %s: %s", session_id, exc)
            update_session_status(session_id, "interrupted")

    asyncio.get_event_loop().run_in_executor(None, _do_scoring)
    return {"status": "scoring"}


@router.patch("/{session_id}/pause")
async def pause_interview(session_id: int):
    session = load_session(session_id)
    if session["status"] != "active":
        raise HTTPException(status_code=400, detail="Can only pause active sessions")
    update_session_status(session_id, "paused")
    return {"status": "paused"}


@router.patch("/{session_id}/resume")
async def resume_interview(session_id: int):
    session = load_session(session_id)
    if session["status"] != "paused":
        raise HTTPException(status_code=400, detail="Can only resume paused sessions")
    update_session_status(session_id, "active")
    return {"status": "active"}


@router.get("/sessions")
async def list_sessions(job_id: int = Query(...)):
    return list_sessions_for_job(job_id)


@router.get("/{session_id}")
async def get_session(session_id: int):
    session = load_session(session_id)
    turns = load_turns(session_id)
    results = load_results(session_id)
    return {"session": session, "turns": turns, "results": results}


@router.delete("/{session_id}")
async def delete_interview(session_id: int):
    delete_session(session_id)
    return {"ok": True}
