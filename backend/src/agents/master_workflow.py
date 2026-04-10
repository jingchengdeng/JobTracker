import logging
import uuid
from typing import TypedDict

from langgraph.graph import StateGraph, END
from langgraph.types import Send

from src.agents.pipeline_tracking import track_node, TrackBehavior
from src.db import get_connection

logger = logging.getLogger(__name__)


class MasterWorkflowState(TypedDict):
    workflow_run_id: str
    # Extraction inputs (matches ExtractionState field names)
    raw_text: str
    url: str
    # Extraction outputs
    extracted: dict | None
    validation_errors: list[str]
    retry_count: int
    # Insert result
    job_id: int | None
    error: str | None
    # Resume resolution
    default_resume_id: int | None
    default_resume_text: str | None
    default_resume_name: str | None


@track_node("master", "resolve_default_resume", TrackBehavior.SINGLE_SHOT)
async def resolve_default_resume(state: MasterWorkflowState) -> dict:
    """Query DB for the default resume (is_default=1)."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT id, extracted_text, name FROM resumes WHERE is_default = 1"
        )
        row = await cursor.fetchone()

    if row and row["extracted_text"]:
        return {
            "default_resume_id": row["id"],
            "default_resume_text": row["extracted_text"],
            "default_resume_name": row["name"],
        }
    return {
        "default_resume_id": None,
        "default_resume_text": None,
        "default_resume_name": None,
    }


async def _should_fan_out(state: MasterWorkflowState) -> str:
    """Conditional edge after insert_job: stop if no valid job_id or error."""
    if not state.get("job_id") or state.get("error"):
        return "end"
    return "resolve_default_resume"


async def fan_out(state: MasterWorkflowState) -> list[Send]:
    """Dispatch parallel branches via Send()."""
    workflow_run_id = state.get("workflow_run_id")
    sends = []
    # LinkedIn branch always runs
    sends.append(Send("linkedin_branch", {
        "job_id": state["job_id"],
        "workflow_run_id": workflow_run_id,
    }))
    # Resume branch only if default resume exists and has text
    if state.get("default_resume_id") and state.get("default_resume_text"):
        sends.append(Send("resume_branch", {
            "job_id": state["job_id"],
            "resume_id": state["default_resume_id"],
            "resume_text": state["default_resume_text"],
            "resume_name": state["default_resume_name"],
            "description": state.get("extracted", {}).get("description") if state.get("extracted") else None,
            "workflow_run_id": workflow_run_id,
        }))
    return sends


async def resume_branch(state: dict) -> dict:
    """Run the full resume tailor pipeline. MUST NOT raise."""
    run_id = None
    try:
        from src.agents.orchestrator import run_pipeline
        async with get_connection() as conn:
            cursor = await conn.execute(
                "INSERT INTO ai_runs (job_id, resume_id, status) VALUES (?, ?, 'pending')",
                (state["job_id"], state["resume_id"]),
            )
            run_id = cursor.lastrowid
            await conn.commit()

        await run_pipeline(
            run_id=run_id,
            job_id=state["job_id"],
            resume_id=state["resume_id"],
            jd_text=state.get("description") or "",
            resume_text=state["resume_text"],
            round_number=0,
            workflow_run_id=state.get("workflow_run_id"),
        )
    except Exception as exc:
        logger.error("Resume tailor branch failed for job %s: %s", state["job_id"], exc)
        if run_id:
            try:
                async with get_connection() as conn:
                    await conn.execute(
                        "UPDATE ai_runs SET status = 'failed', error = ? WHERE id = ? AND status != 'completed'",
                        (str(exc), run_id),
                    )
                    await conn.commit()
            except Exception:
                logger.error("Failed to mark run %s as failed", run_id)
    return {}


async def linkedin_branch(state: dict) -> dict:
    """Run the LinkedIn research pipeline. MUST NOT raise."""
    try:
        from src.agents.linkedin_db import create_search
        from src.agents.linkedin_pipeline import run_linkedin_pipeline
        search_id = await create_search(job_id=state["job_id"])
        await run_linkedin_pipeline(search_id, state["job_id"])
    except Exception as exc:
        logger.error("LinkedIn research branch failed for job %s: %s", state["job_id"], exc)
    return {}


def build_master_graph() -> StateGraph:
    from src.agents.extraction_pipeline import (
        extract_fields,
        validate_fields,
        insert_job,
        _should_retry,
        _handle_failure,
    )

    fail_node = track_node("master", "fail_node", TrackBehavior.SINGLE_SHOT)(_handle_failure)

    graph = StateGraph(MasterWorkflowState)

    # Extraction nodes
    graph.add_node("extract_fields", extract_fields)
    graph.add_node("validate_fields", validate_fields)
    graph.add_node("insert_job", insert_job)
    graph.add_node("fail", fail_node)

    # Post-insert nodes
    graph.add_node("resolve_default_resume", resolve_default_resume)
    graph.add_node("resume_branch", resume_branch)
    graph.add_node("linkedin_branch", linkedin_branch)

    # Edges
    graph.set_entry_point("extract_fields")
    graph.add_edge("extract_fields", "validate_fields")
    graph.add_conditional_edges(
        "validate_fields",
        _should_retry,
        {
            "insert_job": "insert_job",
            "extract_fields": "extract_fields",
            "fail": "fail",
        },
    )
    graph.add_conditional_edges(
        "insert_job",
        _should_fan_out,
        {
            "resolve_default_resume": "resolve_default_resume",
            "end": END,
        },
    )
    graph.add_conditional_edges(
        "resolve_default_resume",
        fan_out,
    )
    graph.add_edge("fail", END)
    graph.add_edge("resume_branch", END)
    graph.add_edge("linkedin_branch", END)

    return graph


_compiled_master_graph = build_master_graph().compile()


async def run_master_workflow(
    raw_text: str, url: str, workflow_run_id: str | None = None,
) -> dict:
    """Run the full master workflow. Returns {job_id, error}."""
    initial_state: MasterWorkflowState = {
        "workflow_run_id": workflow_run_id or str(uuid.uuid4()),
        "raw_text": raw_text,
        "url": url,
        "extracted": None,
        "validation_errors": [],
        "retry_count": 0,
        "job_id": None,
        "error": None,
        "default_resume_id": None,
        "default_resume_text": None,
        "default_resume_name": None,
    }

    try:
        result = await _compiled_master_graph.ainvoke(initial_state)
        return {"job_id": result.get("job_id"), "error": result.get("error")}
    except Exception as exc:
        logger.error("Master workflow exception: %s: %s", type(exc).__name__, exc)
        return {"job_id": None, "error": str(exc)}
