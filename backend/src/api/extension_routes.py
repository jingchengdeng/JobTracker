import asyncio
import os
import re
import logging
import uuid
from pathlib import Path

import aiofiles
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from src.agents.extraction_pipeline import run_extraction_pipeline
from src.agents.master_workflow import resolve_default_resume, fan_out, resume_branch, linkedin_branch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/extension")

_background_tasks: set[asyncio.Task] = set()

DEFAULT_EXTRACTIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "extractions"
)

NEXTJS_JOBS_URL = "http://localhost:3000/api/jobs"


class ExtractedFields(BaseModel):
    title: str | None = None
    company: str | None = None
    description: str | None = None
    location: str | None = None
    workMode: str | None = None
    salary: str | None = None
    jobType: str | None = None


class ExtractRequest(BaseModel):
    url: str
    extracted: ExtractedFields
    rawPanelText: str
    timestamp: str


def _slugify(text: str, max_len: int = 50) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len]


def _get_extractions_dir() -> Path:
    d = Path(os.environ.get("EXTRACTIONS_DIR", DEFAULT_EXTRACTIONS_DIR))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _format_extraction(req: ExtractRequest) -> str:
    lines = ["=== URL ===", req.url, ""]

    lines.append("=== EXTRACTED FIELDS ===")
    fields = req.extracted
    for name in ["title", "company", "location", "workMode", "salary", "jobType"]:
        val = getattr(fields, name, None)
        if val is not None:
            lines.append(f"{name}: {val}")

    if fields.description:
        preview = fields.description[:200]
        if len(fields.description) > 200:
            preview += "..."
        lines.append(f"description: {preview}")

    lines.append("")
    lines.append("=== RAW PANEL TEXT ===")
    lines.append(req.rawPanelText)
    return "\n".join(lines)


def _slug_from_url(url: str) -> str:
    """Return the last meaningful path segment of a URL as a slug."""
    path = urlparse(url).path
    segments = [s for s in path.split("/") if s]
    last = segments[-1] if segments else ""
    return _slugify(last) if last else "untitled"


@router.post("/extract")
async def extract(req: ExtractRequest):
    extractions_dir = _get_extractions_dir()

    if req.extracted.title:
        slug = _slugify(req.extracted.title)
    else:
        slug = _slug_from_url(req.url)
    safe_timestamp = _slugify(req.timestamp, max_len=30)
    filename = f"{safe_timestamp}_{slug}.txt"
    filepath = extractions_dir / filename

    content = _format_extraction(req)
    async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
        await f.write(content)

    logger.info("Saved extraction to %s", filepath)

    workflow_run_id = str(uuid.uuid4())

    # Check for duplicate by URL
    if req.url and req.url.strip():
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    NEXTJS_JOBS_URL, params={"url": req.url}
                )
                resp.raise_for_status()
                existing_jobs = resp.json()
            if existing_jobs:
                logger.info("Duplicate detected for URL: %s", req.url)
                return {
                    "success": True,
                    "filename": filename,
                    "duplicate": True,
                    "existing_job_id": existing_jobs[0]["id"],
                    "message": "Already saved",
                }
        except Exception as exc:
            logger.warning("Duplicate check failed, proceeding with pipeline: %s", exc)

    # Run LLM extraction pipeline
    job_id = None
    extraction_error = None
    pipeline_result = {}
    try:
        pipeline_result = await run_extraction_pipeline(
            req.rawPanelText, req.url, workflow_run_id=workflow_run_id,
        )
        job_id = pipeline_result.get("job_id")
        extraction_error = pipeline_result.get("error")
        if extraction_error:
            logger.error("Extraction pipeline error: %s", extraction_error)
    except Exception as exc:
        logger.error("Extraction pipeline failed: %s", exc)
        extraction_error = str(exc)

    # Fire-and-forget: fan out to resume tailor + LinkedIn research
    if job_id and not extraction_error:
        async def _fan_out_background():
            try:
                resume_state = await resolve_default_resume({
                    "job_id": job_id,
                    "workflow_run_id": workflow_run_id,
                })

                extracted = pipeline_result.get("extracted") or {}

                full_state = {
                    "job_id": job_id,
                    "workflow_run_id": workflow_run_id,
                    "extracted": {"description": extracted.get("description")} if extracted else None,
                    "default_resume_id": resume_state.get("default_resume_id"),
                    "default_resume_text": resume_state.get("default_resume_text"),
                    "default_resume_name": resume_state.get("default_resume_name"),
                }
                sends = await fan_out(full_state)

                tasks = []
                for send in sends:
                    if send.node == "resume_branch":
                        tasks.append(resume_branch(send.arg))
                    elif send.node == "linkedin_branch":
                        tasks.append(linkedin_branch(send.arg))
                if tasks:
                    await asyncio.gather(*tasks)
            except Exception as exc:
                logger.error("Fan-out background failed: %s", exc)

        task = asyncio.create_task(_fan_out_background())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    result = {
        "success": True,
        "filename": filename,
        "job_id": job_id,
        "workflow_run_id": workflow_run_id,
    }
    if extraction_error:
        result["extraction_error"] = extraction_error
    return result
