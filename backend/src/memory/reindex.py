import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from src.db import get_connection
from src.memory.collection_resolver import collection_for_signature
from src.memory.embedding_state import set_active_signature, get_active_signature
from src.memory.rag import index_resume_into, mark_resume_failed, mark_resume_ok
from src.memory.retry import with_retry

logger = logging.getLogger("jobtracker.reindex")


@dataclass
class ReindexJob:
    job_id: str
    status: str  # "running" | "completed" | "failed"
    target_signature: str
    started_at: str
    completed_at: Optional[str] = None
    total: int = 0
    succeeded: list[int] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)
    current_resume_id: Optional[int] = None
    task: Optional[asyncio.Task] = None

    def to_json(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "target_signature": self.target_signature,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total": self.total,
            "succeeded": list(self.succeeded),
            "failed": list(self.failed),
            "current_resume_id": self.current_resume_id,
        }


_jobs: dict[str, ReindexJob] = {}
_lock = asyncio.Lock()


def get_job(job_id: str) -> Optional[ReindexJob]:
    return _jobs.get(job_id)


def active_job() -> Optional[ReindexJob]:
    for job in _jobs.values():
        if job.status == "running":
            return job
    return None


async def start_reindex_job(
    *,
    target_signature: str,
    provider: str,
    model: str,
    resume_ids: Optional[list[int]] = None,
) -> str:
    """Kick off a reindex job; returns job_id. Raises if one is already running."""
    async with _lock:
        if active_job() is not None:
            raise RuntimeError("A reindex job is already running")
        job = ReindexJob(
            job_id=str(uuid.uuid4()),
            status="running",
            target_signature=target_signature,
            started_at=_now_iso(),
        )
        _jobs[job.job_id] = job
        job.task = asyncio.create_task(
            _run_job(job, provider=provider, model=model, resume_ids=resume_ids)
        )
    return job.job_id


async def _run_job(
    job: ReindexJob,
    *,
    provider: str,
    model: str,
    resume_ids: Optional[list[int]],
) -> None:
    try:
        collection = await collection_for_signature(
            job.target_signature, provider=provider, model=model
        )

        resumes = await _fetch_resumes(resume_ids)
        job.total = len(resumes)

        for r in resumes:
            job.current_resume_id = r["id"]
            if not r["extracted_text"]:
                await mark_resume_failed(r["id"], "No extracted text on file")
                job.failed.append({"resume_id": r["id"], "error": "No extracted text on file"})
                continue
            try:
                async def op(resume=r):
                    await index_resume_into(collection, resume["id"], resume["name"], resume["extracted_text"])
                await with_retry(op, retries=3, backoff=(1.0, 2.0, 4.0))
                await mark_resume_ok(r["id"], job.target_signature)
                job.succeeded.append(r["id"])
            except Exception as exc:
                logger.warning("Resume %s reindex failed: %s", r["id"], exc)
                await mark_resume_failed(r["id"], str(exc))
                job.failed.append({"resume_id": r["id"], "error": str(exc)})

        job.current_resume_id = None
        job.status = "completed"
        job.completed_at = _now_iso()

        await _maybe_flip_pointer(
            job.target_signature,
            was_full=resume_ids is None,
            had_failures=bool(job.failed),
        )
    except Exception as exc:
        logger.exception("Reindex job %s failed unexpectedly", job.job_id)
        job.status = "failed"
        job.completed_at = _now_iso()
        job.failed.append({"resume_id": job.current_resume_id, "error": str(exc)})


async def _maybe_flip_pointer(target_signature: str, *, was_full: bool, had_failures: bool) -> None:
    if was_full and not had_failures:
        logger.info("Flipping active_signature to %s (clean full reindex)", target_signature)
        await set_active_signature(target_signature)
        return
    # Post-retry hook: if every resume is now at target_signature with ok status, flip
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN last_index_signature = ? AND last_index_status = 'ok' THEN 1 ELSE 0 END) AS ok_count "
            "FROM resumes",
            (target_signature,),
        )
        row = await cursor.fetchone()
    if row["total"] > 0 and row["ok_count"] == row["total"]:
        logger.info("Flipping active_signature to %s (post-retry convergence)", target_signature)
        await set_active_signature(target_signature)


async def _fetch_resumes(resume_ids: Optional[list[int]]) -> list[dict]:
    async with get_connection() as conn:
        if resume_ids is None:
            cursor = await conn.execute(
                "SELECT id, name, extracted_text FROM resumes ORDER BY id"
            )
        else:
            placeholders = ",".join("?" * len(resume_ids))
            cursor = await conn.execute(
                f"SELECT id, name, extracted_text FROM resumes WHERE id IN ({placeholders}) ORDER BY id",
                tuple(resume_ids),
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
