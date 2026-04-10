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

_background_tasks: set[asyncio.Task] = set()


class ExtractTextRequest(BaseModel):
    resume_id: int
    file_path: str


@router.post("/extract-text")
async def extract_resume_text(req: ExtractTextRequest):
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    data_dir = (project_root / "data").resolve()
    resolved = Path(req.file_path).resolve()
    if not str(resolved).startswith(str(data_dir) + "/"):
        raise HTTPException(status_code=400, detail="Invalid file path")

    try:
        text = await asyncio.to_thread(extract_text, str(resolved))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    async with get_connection() as conn:
        await conn.execute(
            "UPDATE resumes SET extracted_text = ? WHERE id = ?",
            (text, req.resume_id),
        )
        await conn.commit()

        cursor = await conn.execute(
            "SELECT name FROM resumes WHERE id = ?", (req.resume_id,)
        )
        row = await cursor.fetchone()

    resume_name = row["name"] if row else f"Resume {req.resume_id}"
    await index_resume(req.resume_id, resume_name, text)

    return {"resume_id": req.resume_id, "char_count": len(text)}


@router.delete("/resumes/{resume_id}/chunks")
async def delete_resume_chunks_route(resume_id: int):
    removed = await delete_resume_chunks(resume_id)
    return {"resume_id": resume_id, "removed": removed}


class CreateRunRequest(BaseModel):
    job_id: int
    resume_id: int


class SendMessageRequest(BaseModel):
    content: str


@router.post("/runs")
async def create_run(req: CreateRunRequest):
    async with get_connection() as conn:
        cursor = await conn.execute("SELECT description FROM jobs WHERE id = ?", (req.job_id,))
        job = await cursor.fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        cursor = await conn.execute(
            "SELECT extracted_text, name FROM resumes WHERE id = ?", (req.resume_id,)
        )
        resume = await cursor.fetchone()
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        if not resume["extracted_text"]:
            raise HTTPException(status_code=400, detail="Resume text not yet extracted")

        cursor = await conn.execute(
            "INSERT INTO ai_runs (job_id, resume_id, status) VALUES (?, ?, 'pending')",
            (req.job_id, req.resume_id),
        )
        run_id = cursor.lastrowid
        await conn.commit()

    async def _background():
        try:
            await run_pipeline(
                run_id=run_id,
                job_id=req.job_id,
                resume_id=req.resume_id,
                jd_text=job["description"],
                resume_text=resume["extracted_text"],
                round_number=0,
            )
        except Exception as exc:
            logger.exception("Pipeline failed: %s", exc)

    task = asyncio.create_task(_background())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {"run_id": run_id, "status": "pending"}


async def _extract_match_score(conn, run_id: int) -> int | None:
    """Return overall_match_score from the latest completed gap_analysis step."""
    cursor = await conn.execute(
        "SELECT result FROM ai_steps "
        "WHERE run_id = ? AND step_type = 'gap_analysis' AND status = 'completed' "
        "ORDER BY version DESC LIMIT 1",
        (run_id,),
    )
    row = await cursor.fetchone()
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
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT r.id, r.status, r.error, r.created_at, r.completed_at, "
            "r.resume_id, res.name AS resume_name, res.version AS resume_version "
            "FROM ai_runs r JOIN resumes res ON res.id = r.resume_id "
            "WHERE r.job_id = ? ORDER BY r.created_at DESC",
            (job_id,),
        )
        rows = await cursor.fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r["id"],
                "resume_id": r["resume_id"],
                "resume_name": r["resume_name"],
                "resume_version": r["resume_version"],
                "status": r["status"],
                "error": r["error"],
                "match_score": await _extract_match_score(conn, r["id"]),
                "created_at": r["created_at"],
                "completed_at": r["completed_at"],
            })
        return result


@router.get("/runs/{run_id}")
async def get_run(run_id: int):
    async with get_connection() as conn:
        cursor = await conn.execute("SELECT * FROM ai_runs WHERE id = ?", (run_id,))
        run = await cursor.fetchone()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        cursor = await conn.execute(
            "SELECT * FROM ai_steps WHERE run_id = ? ORDER BY id", (run_id,)
        )
        steps = await cursor.fetchall()

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
    async with get_connection() as conn:
        cursor = await conn.execute("SELECT * FROM ai_runs WHERE id = ?", (run_id,))
        run = await cursor.fetchone()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        cursor = await conn.execute("SELECT description FROM jobs WHERE id = ?", (run["job_id"],))
        job = await cursor.fetchone()
        cursor = await conn.execute(
            "SELECT extracted_text FROM resumes WHERE id = ?", (run["resume_id"],)
        )
        resume = await cursor.fetchone()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    round_num = await get_current_round(run_id)
    await save_message(run_id, "user", req.content, round_num)

    async with get_connection() as conn:
        await conn.execute("UPDATE ai_runs SET status = 'running' WHERE id = ?", (run_id,))
        await conn.commit()

    job_id_val = run["job_id"]
    resume_id_val = run["resume_id"]
    jd_text_val = job["description"]
    resume_text_val = resume["extracted_text"]
    user_content = req.content

    async def _background():
        await _classify_and_run_pipeline(
            run_id, job_id_val, resume_id_val,
            jd_text_val, resume_text_val,
            user_content, round_num,
        )

    task = asyncio.create_task(_background())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {"status": "running", "round": round_num}


async def _classify_and_run_pipeline(
    run_id, job_id, resume_id, jd_text, resume_text,
    user_content, round_num,
):
    """Classify the follow-up, save the ack, then run the pipeline."""
    summary = await get_conversation_summary(run_id)

    try:
        classifier_result = await classify_followup(user_content, summary or "")
    except Exception:
        ack_text = "Working on your refine..."
        needs_jd = needs_gap = needs_sug = needs_rew = True
    else:
        ack_text = classifier_result.response_message
        needs_jd = classifier_result.needs_jd_analysis
        needs_gap = classifier_result.needs_gap_analysis
        needs_sug = classifier_result.needs_suggestions
        needs_rew = classifier_result.needs_rewrite

    await save_message(run_id, "assistant", ack_text, round_num)

    recent = await get_recent_messages(run_id)

    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT step_type, result FROM ai_steps WHERE run_id = ? AND status = 'completed' ORDER BY version DESC",
            (run_id,),
        )
        steps = await cursor.fetchall()

    previous_state = {}
    for step in steps:
        if step["step_type"] not in previous_state:
            previous_state[step["step_type"]] = step["result"]

    try:
        await run_pipeline(
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
        async with get_connection() as conn:
            await conn.execute(
                "UPDATE ai_runs SET status = 'failed', error = 'Pipeline error' WHERE id = ? AND status = 'running'",
                (run_id,),
            )
            await conn.commit()
        return

    try:
        llm = await get_chat_model()
        await summarize_old_rounds(run_id, llm)
    except Exception as exc:
        logger.warning("summarize_old_rounds failed (non-fatal): %s", exc)


@router.get("/runs/{run_id}/messages")
async def get_messages(run_id: int):
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT role, content, round_number, created_at FROM ai_messages "
            "WHERE run_id = ? ORDER BY round_number, id",
            (run_id,),
        )
        messages = await cursor.fetchall()
        cursor = await conn.execute(
            "SELECT conversation_summary FROM ai_runs WHERE id = ?", (run_id,)
        )
        summary = await cursor.fetchone()

    return {
        "messages": [dict(m) for m in messages],
        "summary": summary["conversation_summary"] if summary else None,
    }


@router.post("/runs/{run_id}/retry")
async def retry_run(run_id: int):
    async with get_connection() as conn:
        cursor = await conn.execute("SELECT * FROM ai_runs WHERE id = ?", (run_id,))
        run = await cursor.fetchone()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        if run["status"] != "failed":
            raise HTTPException(status_code=400, detail="Can only retry failed runs")

        await conn.execute(
            "UPDATE ai_runs SET status = 'pending', error = NULL WHERE id = ?", (run_id,)
        )
        await conn.commit()

        cursor = await conn.execute("SELECT description FROM jobs WHERE id = ?", (run["job_id"],))
        job = await cursor.fetchone()
        cursor = await conn.execute(
            "SELECT extracted_text FROM resumes WHERE id = ?", (run["resume_id"],)
        )
        resume = await cursor.fetchone()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    async def _background():
        try:
            await run_pipeline(
                run_id=run_id,
                job_id=run["job_id"],
                resume_id=run["resume_id"],
                jd_text=job["description"],
                resume_text=resume["extracted_text"],
                round_number=0,
            )
        except Exception as exc:
            logger.exception("Pipeline failed: %s", exc)

    task = asyncio.create_task(_background())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {"status": "pending"}


@router.delete("/runs/{run_id}", status_code=204)
async def delete_run(run_id: int):
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT status FROM ai_runs WHERE id = ?", (run_id,)
        )
        run = await cursor.fetchone()
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        if run["status"] == "running":
            raise HTTPException(status_code=409, detail="run_in_progress")
        await conn.execute("DELETE FROM ai_messages WHERE run_id = ?", (run_id,))
        await conn.execute("DELETE FROM ai_steps WHERE run_id = ?", (run_id,))
        await conn.execute("DELETE FROM ai_runs WHERE id = ?", (run_id,))
        await conn.commit()
    return None
