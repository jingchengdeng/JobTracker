from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.db import get_connection
from src.memory.embedding_state import get_active_signature
from src.memory.reindex import active_job, get_job, start_reindex_job
from src.services.embeddings import configured_signature
from src.auth.credentials import load_model_config

router = APIRouter(prefix="/api/embedding")


class ReindexRequest(BaseModel):
    resume_ids: list[int] | None = None


@router.get("/status")
async def embedding_status():
    active_sig = await get_active_signature()
    configured_sig = configured_signature()

    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT id, name, last_index_signature, last_index_status, last_index_error "
            "FROM resumes ORDER BY id"
        )
        rows = await cursor.fetchall()

    resumes = [
        {
            "id": r["id"],
            "name": r["name"],
            "last_index_signature": r["last_index_signature"],
            "last_index_status": r["last_index_status"],
            "last_index_error": r["last_index_error"],
        }
        for r in rows
    ]

    job = active_job()
    return {
        "active_signature": active_sig,
        "configured_signature": configured_sig,
        "resumes": resumes,
        "active_job": job.to_json() if job else None,
    }


@router.post("/reindex")
async def reindex(req: ReindexRequest):
    running = active_job()
    if running is not None:
        raise HTTPException(
            status_code=409,
            detail={"error": "reindex_in_progress", "job_id": running.job_id},
        )

    config = load_model_config()
    embedding = config["embedding"]
    target_sig = configured_signature()
    try:
        job_id = await start_reindex_job(
            target_signature=target_sig,
            provider=embedding["provider"],
            model=embedding["model"],
            resume_ids=req.resume_ids,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": "reindex_in_progress", "message": str(exc)},
        )
    return {"job_id": job_id, "target_signature": target_sig}


@router.get("/reindex/{job_id}")
async def get_reindex_job(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_json()
