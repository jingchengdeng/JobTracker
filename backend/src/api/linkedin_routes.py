import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.agents.linkedin_db import (
    create_search, load_search, load_contacts, delete_search, load_latest_search_for_job,
)
from src.agents.linkedin_pipeline import run_linkedin_pipeline
from src.db import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/linkedin")

_background_tasks: set[asyncio.Task] = set()


class SearchRequest(BaseModel):
    job_id: int


@router.post("/search")
async def start_search(req: SearchRequest):
    # Validate job exists
    conn = get_connection()
    try:
        row = conn.execute("SELECT id FROM jobs WHERE id = ?", (req.job_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    search_id = create_search(job_id=req.job_id)
    task = asyncio.create_task(run_linkedin_pipeline(search_id, req.job_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return {"search_id": search_id, "status": "running"}


@router.get("/job/{job_id}")
async def get_latest_for_job(job_id: int):
    """Get the latest search for a job, if any."""
    search = load_latest_search_for_job(job_id)
    if not search:
        return {"search": None}
    contacts = load_contacts(search["id"])
    company = None
    if search.get("company_data_json") and search["company_data_json"] != "{}":
        company = {
            "domain": search.get("company_domain"),
            "summary": search.get("company_summary"),
            "data": json.loads(search["company_data_json"]),
        }
    return {
        "search": {
            "id": search["id"],
            "status": search["status"],
            "started_at": search["started_at"],
            "completed_at": search.get("completed_at"),
        },
        "company": company,
        "contacts": [dict(c) for c in contacts],
    }


@router.get("/{search_id}")
async def get_search(search_id: int):
    try:
        search = load_search(search_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Search not found")

    contacts = load_contacts(search_id)
    company = None
    if search.get("company_data_json") and search["company_data_json"] != "{}":
        company = {
            "domain": search.get("company_domain"),
            "summary": search.get("company_summary"),
            "data": json.loads(search["company_data_json"]),
        }

    return {
        "search": {
            "id": search["id"],
            "status": search["status"],
            "started_at": search["started_at"],
            "completed_at": search.get("completed_at"),
        },
        "company": company,
        "contacts": [dict(c) for c in contacts],
    }


@router.delete("/{search_id}")
async def delete_search_endpoint(search_id: int):
    try:
        load_search(search_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Search not found")
    delete_search(search_id)
    return {"ok": True}
