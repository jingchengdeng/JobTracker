import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.db import get_connection
from src.memory.rag import index_resume, delete_resume_chunks
from src.services.text_extract import extract_text
from src.agents.orchestrator import run_pipeline
from src.memory.conversation import (
    save_message,
    get_recent_messages,
    get_current_round,
    get_conversation_summary,
    summarize_old_rounds,
)
from src.models.provider import get_chat_model

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
        run_pipeline,
        run_id,
        req.job_id,
        req.resume_id,
        job["description"],
        resume["extracted_text"],
    )

    return {"run_id": run_id, "status": "pending"}


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

    round_num = get_current_round(run_id)
    save_message(run_id, "user", req.content, round_num)

    recent = get_recent_messages(run_id)
    summary = get_conversation_summary(run_id)

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

    asyncio.get_event_loop().run_in_executor(
        None,
        lambda: _run_followup(
            run_id, run["job_id"], run["resume_id"],
            job["description"], resume["extracted_text"],
            req.content, summary, recent, previous_state, round_num,
        ),
    )

    return {"status": "running", "round": round_num}


def _run_followup(
    run_id, job_id, resume_id, jd_text, resume_text,
    message, summary, recent, previous_state, round_num,
):
    """Run the pipeline for a follow-up message, then save the response and summarize."""
    result = run_pipeline(
        run_id=run_id,
        job_id=job_id,
        resume_id=resume_id,
        jd_text=jd_text,
        resume_text=resume_text,
        is_followup=True,
        followup_message=message,
        conversation_summary=summary,
        recent_messages=recent,
        previous_state=previous_state,
    )

    response_parts = []
    if result.get("rewrite"):
        response_parts.append("Rewrite updated.")
    if result.get("suggestions"):
        response_parts.append("Suggestions updated.")
    if result.get("gap_analysis"):
        response_parts.append("Gap analysis updated.")

    assistant_content = " ".join(response_parts) if response_parts else "Pipeline completed."
    save_message(run_id, "assistant", assistant_content, round_num)

    try:
        llm = get_chat_model()
        summarize_old_rounds(run_id, llm)
    except Exception:
        pass


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

    asyncio.get_event_loop().run_in_executor(
        None,
        run_pipeline,
        run_id, run["job_id"], run["resume_id"],
        job["description"], resume["extracted_text"],
    )

    return {"status": "pending"}
