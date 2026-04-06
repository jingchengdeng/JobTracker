import asyncio
import json as _json
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.db import get_connection
from src.memory.rag import index_resume, delete_resume_chunks
from src.services.text_extract import extract_text
from src.agents.orchestrator import run_pipeline
from src.agents.classifier import classify_followup
from src.memory.conversation import (
    save_message,
    get_recent_messages,
    get_current_round,
    get_conversation_summary,
    summarize_old_rounds,
)
from src.models.provider import get_chat_model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


class ExtractTextRequest(BaseModel):
    resume_id: int
    file_path: str


@router.post("/extract-text")
async def extract_resume_text(req: ExtractTextRequest):
    try:
        text = extract_text(req.file_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    conn = get_connection()
    conn.execute(
        "UPDATE resumes SET extracted_text = ? WHERE id = ?",
        (text, req.resume_id),
    )
    conn.commit()

    row = conn.execute(
        "SELECT name FROM resumes WHERE id = ?", (req.resume_id,)
    ).fetchone()
    conn.close()

    resume_name = row["name"] if row else f"Resume {req.resume_id}"
    index_resume(req.resume_id, resume_name, text)

    return {"resume_id": req.resume_id, "char_count": len(text)}


@router.delete("/resumes/{resume_id}/chunks")
async def delete_resume_chunks_route(resume_id: int):
    removed = delete_resume_chunks(resume_id)
    return {"resume_id": resume_id, "removed": removed}


class CreateRunRequest(BaseModel):
    job_id: int
    resume_id: int


class SendMessageRequest(BaseModel):
    content: str


@router.post("/runs")
async def create_run(req: CreateRunRequest):
    conn = get_connection()

    job = conn.execute("SELECT description FROM jobs WHERE id = ?", (req.job_id,)).fetchone()
    if not job:
        conn.close()
        raise HTTPException(status_code=404, detail="Job not found")

    resume = conn.execute(
        "SELECT extracted_text, name FROM resumes WHERE id = ?", (req.resume_id,)
    ).fetchone()
    if not resume:
        conn.close()
        raise HTTPException(status_code=404, detail="Resume not found")
    if not resume["extracted_text"]:
        conn.close()
        raise HTTPException(status_code=400, detail="Resume text not yet extracted")

    cursor = conn.execute(
        "INSERT INTO ai_runs (job_id, resume_id, status) VALUES (?, ?, 'pending')",
        (req.job_id, req.resume_id),
    )
    run_id = cursor.lastrowid
    conn.commit()
    conn.close()

    asyncio.get_event_loop().run_in_executor(
        None,
        lambda: run_pipeline(
            run_id=run_id,
            job_id=req.job_id,
            resume_id=req.resume_id,
            jd_text=job["description"],
            resume_text=resume["extracted_text"],
            round_number=0,
        ),
    )

    return {"run_id": run_id, "status": "pending"}


def _extract_match_score(conn, run_id: int) -> int | None:
    """Return overall_match_score from the latest completed gap_analysis step."""
    row = conn.execute(
        "SELECT result FROM ai_steps "
        "WHERE run_id = ? AND step_type = 'gap_analysis' AND status = 'completed' "
        "ORDER BY version DESC LIMIT 1",
        (run_id,),
    ).fetchone()
    if not row or not row["result"]:
        return None
    try:
        data = _json.loads(row["result"])
    except (ValueError, TypeError):
        return None
    score = data.get("overall_match_score") if isinstance(data, dict) else None
    return score if isinstance(score, int) else None


@router.get("/jobs/{job_id}/runs")
async def list_runs_for_job(job_id: int):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT r.id, r.status, r.error, r.created_at, r.completed_at, "
            "r.resume_id, res.name AS resume_name, res.version AS resume_version "
            "FROM ai_runs r JOIN resumes res ON res.id = r.resume_id "
            "WHERE r.job_id = ? ORDER BY r.created_at DESC",
            (job_id,),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "resume_id": r["resume_id"],
                "resume_name": r["resume_name"],
                "resume_version": r["resume_version"],
                "status": r["status"],
                "error": r["error"],
                "match_score": _extract_match_score(conn, r["id"]),
                "created_at": r["created_at"],
                "completed_at": r["completed_at"],
            }
            for r in rows
        ]
    finally:
        conn.close()


@router.get("/runs/{run_id}")
async def get_run(run_id: int):
    conn = get_connection()

    run = conn.execute("SELECT * FROM ai_runs WHERE id = ?", (run_id,)).fetchone()
    if not run:
        conn.close()
        raise HTTPException(status_code=404, detail="Run not found")

    steps = conn.execute(
        "SELECT * FROM ai_steps WHERE run_id = ? ORDER BY id", (run_id,)
    ).fetchall()

    conn.close()

    return {
        "id": run["id"],
        "job_id": run["job_id"],
        "resume_id": run["resume_id"],
        "status": run["status"],
        "error": run["error"],
        "created_at": run["created_at"],
        "completed_at": run["completed_at"],
        "steps": [dict(s) for s in steps],
    }


@router.post("/runs/{run_id}/message")
async def send_message(run_id: int, req: SendMessageRequest):
    conn = get_connection()

    run = conn.execute("SELECT * FROM ai_runs WHERE id = ?", (run_id,)).fetchone()
    if not run:
        conn.close()
        raise HTTPException(status_code=404, detail="Run not found")

    job = conn.execute("SELECT description FROM jobs WHERE id = ?", (run["job_id"],)).fetchone()
    resume = conn.execute(
        "SELECT extracted_text FROM resumes WHERE id = ?", (run["resume_id"],)
    ).fetchone()

    conn.close()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    round_num = get_current_round(run_id)
    save_message(run_id, "user", req.content, round_num)

    conn = get_connection()
    conn.execute("UPDATE ai_runs SET status = 'running' WHERE id = ?", (run_id,))
    conn.commit()
    conn.close()

    job_id_val = run["job_id"]
    resume_id_val = run["resume_id"]
    jd_text_val = job["description"]
    resume_text_val = resume["extracted_text"]
    user_content = req.content

    asyncio.get_event_loop().run_in_executor(
        None,
        lambda: _classify_and_run_pipeline(
            run_id, job_id_val, resume_id_val,
            jd_text_val, resume_text_val,
            user_content, round_num,
        ),
    )

    return {"status": "running", "round": round_num}


def _classify_and_run_pipeline(
    run_id, job_id, resume_id, jd_text, resume_text,
    user_content, round_num,
):
    """Classify the follow-up, save the ack, then run the pipeline."""
    summary = get_conversation_summary(run_id)

    try:
        classifier_result = classify_followup(user_content, summary or "")
    except Exception:
        ack_text = "Working on your refine..."
        needs_jd = needs_gap = needs_sug = needs_rew = True
    else:
        ack_text = classifier_result.response_message
        needs_jd = classifier_result.needs_jd_analysis
        needs_gap = classifier_result.needs_gap_analysis
        needs_sug = classifier_result.needs_suggestions
        needs_rew = classifier_result.needs_rewrite

    save_message(run_id, "assistant", ack_text, round_num)

    recent = get_recent_messages(run_id)

    conn = get_connection()
    steps = conn.execute(
        "SELECT step_type, result FROM ai_steps WHERE run_id = ? AND status = 'completed' ORDER BY version DESC",
        (run_id,),
    ).fetchall()
    conn.close()

    previous_state = {}
    for step in steps:
        if step["step_type"] not in previous_state:
            previous_state[step["step_type"]] = step["result"]

    try:
        run_pipeline(
            run_id=run_id,
            job_id=job_id,
            resume_id=resume_id,
            jd_text=jd_text,
            resume_text=resume_text,
            round_number=round_num,
            previous_state=previous_state,
            conversation_summary=summary,
            recent_messages=recent,
            needs_jd_analysis=needs_jd,
            needs_gap_analysis=needs_gap,
            needs_suggestions=needs_sug,
            needs_rewrite=needs_rew,
        )
    except Exception:
        logger.exception("Pipeline failed for run %s round %s", run_id, round_num)
        conn = get_connection()
        conn.execute(
            "UPDATE ai_runs SET status = 'failed', error = 'Pipeline error' WHERE id = ? AND status = 'running'",
            (run_id,),
        )
        conn.commit()
        conn.close()
        return

    try:
        llm = get_chat_model()
        summarize_old_rounds(run_id, llm)
    except Exception as exc:
        logger.warning("summarize_old_rounds failed (non-fatal): %s", exc)


@router.get("/runs/{run_id}/messages")
async def get_messages(run_id: int):
    conn = get_connection()
    messages = conn.execute(
        "SELECT role, content, round_number, created_at FROM ai_messages "
        "WHERE run_id = ? ORDER BY round_number, id",
        (run_id,),
    ).fetchall()
    summary = conn.execute(
        "SELECT conversation_summary FROM ai_runs WHERE id = ?", (run_id,)
    ).fetchone()
    conn.close()

    return {
        "messages": [dict(m) for m in messages],
        "summary": summary["conversation_summary"] if summary else None,
    }


@router.post("/runs/{run_id}/retry")
async def retry_run(run_id: int):
    conn = get_connection()
    run = conn.execute("SELECT * FROM ai_runs WHERE id = ?", (run_id,)).fetchone()
    if not run:
        conn.close()
        raise HTTPException(status_code=404, detail="Run not found")

    if run["status"] != "failed":
        conn.close()
        raise HTTPException(status_code=400, detail="Can only retry failed runs")

    conn.execute(
        "UPDATE ai_runs SET status = 'pending', error = NULL WHERE id = ?", (run_id,)
    )
    conn.commit()

    job = conn.execute("SELECT description FROM jobs WHERE id = ?", (run["job_id"],)).fetchone()
    resume = conn.execute(
        "SELECT extracted_text FROM resumes WHERE id = ?", (run["resume_id"],)
    ).fetchone()
    conn.close()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    asyncio.get_event_loop().run_in_executor(
        None,
        lambda: run_pipeline(
            run_id=run_id,
            job_id=run["job_id"],
            resume_id=run["resume_id"],
            jd_text=job["description"],
            resume_text=resume["extracted_text"],
            round_number=0,
        ),
    )

    return {"status": "pending"}


@router.delete("/runs/{run_id}", status_code=204)
async def delete_run(run_id: int):
    conn = get_connection()
    try:
        run = conn.execute(
            "SELECT status FROM ai_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        if run["status"] == "running":
            raise HTTPException(status_code=409, detail="run_in_progress")
        conn.execute("BEGIN")
        conn.execute("DELETE FROM ai_messages WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM ai_steps WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM ai_runs WHERE id = ?", (run_id,))
        conn.commit()
    finally:
        conn.close()
    return None
