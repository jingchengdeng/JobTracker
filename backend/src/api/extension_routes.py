import os
import re
import logging
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from src.agents.extraction_pipeline import run_extraction_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/extension")

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
    filepath.write_text(content, encoding="utf-8")

    logger.info("Saved extraction to %s", filepath)

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
    try:
        pipeline_result = await run_extraction_pipeline(req.rawPanelText, req.url)
        job_id = pipeline_result.get("job_id")
        extraction_error = pipeline_result.get("error")
    except Exception as exc:
        logger.error("Extraction pipeline failed: %s", exc)
        extraction_error = str(exc)

    result = {"success": True, "filename": filename, "job_id": job_id}
    if extraction_error:
        result["extraction_error"] = extraction_error
    return result
