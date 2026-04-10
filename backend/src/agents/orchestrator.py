import uuid
from typing import TypedDict, Optional

from langgraph.graph import StateGraph, END

from src.agents.resume_agent import (
    step_jd_analysis,
    step_rag_retrieval,
    step_gap_analysis,
    step_suggestions,
    step_rewrite,
)
from src.db import get_connection
from src.agents.pipeline_tracking import _format_pipeline_error


class ResumeAgentState(TypedDict):
    workflow_run_id: str
    job_id: int
    resume_id: int
    run_id: int
    jd_text: str
    resume_text: str
    jd_analysis: Optional[str]
    rag_chunks: Optional[list[str]]
    gap_analysis: Optional[str]
    suggestions: Optional[str]
    rewrite: Optional[str]
    conversation_summary: Optional[str]
    recent_messages: list[dict]
    user_preferences: list[str]
    needs_jd_analysis: bool
    needs_gap_analysis: bool
    needs_suggestions: bool
    needs_rewrite: bool
    round_number: int


def _should_run(step_type: str):
    """Create a conditional edge function for a step."""
    flag_map = {
        "jd_analysis": "needs_jd_analysis",
        "rag_retrieval": "needs_gap_analysis",
        "gap_analysis": "needs_gap_analysis",
        "suggestions": "needs_suggestions",
        "rewrite": "needs_rewrite",
    }
    flag = flag_map[step_type]

    def check(state: ResumeAgentState) -> str:
        if state.get(flag, True):
            return step_type
        steps = ["jd_analysis", "rag_retrieval", "gap_analysis", "suggestions", "rewrite"]
        current_idx = steps.index(step_type)
        for next_step in steps[current_idx + 1:]:
            next_flag = flag_map.get(next_step, "")
            if state.get(next_flag, True):
                return next_step
        return "end"

    return check


def build_graph() -> StateGraph:
    """Build the LangGraph workflow for resume analysis."""
    graph = StateGraph(ResumeAgentState)

    graph.add_node("jd_analysis", step_jd_analysis)
    graph.add_node("rag_retrieval", step_rag_retrieval)
    graph.add_node("gap_analysis", step_gap_analysis)
    graph.add_node("suggestions", step_suggestions)
    graph.add_node("rewrite", step_rewrite)

    graph.set_conditional_entry_point(
        _should_run("jd_analysis"),
        {
            "jd_analysis": "jd_analysis",
            "rag_retrieval": "rag_retrieval",
            "gap_analysis": "gap_analysis",
            "suggestions": "suggestions",
            "rewrite": "rewrite",
            "end": END,
        },
    )

    graph.add_edge("jd_analysis", "rag_retrieval")
    graph.add_edge("rag_retrieval", "gap_analysis")

    graph.add_conditional_edges(
        "gap_analysis",
        _should_run("suggestions"),
        {
            "suggestions": "suggestions",
            "rewrite": "rewrite",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "suggestions",
        _should_run("rewrite"),
        {
            "rewrite": "rewrite",
            "end": END,
        },
    )

    graph.add_edge("rewrite", END)

    return graph


workflow = build_graph().compile()



async def create_ai_run(state: ResumeAgentState) -> ResumeAgentState:
    """Graph node: create ai_runs record, set status to running."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "INSERT INTO ai_runs (job_id, resume_id, status) VALUES (?, ?, 'running')",
            (state["job_id"], state["resume_id"]),
        )
        run_id = cursor.lastrowid
        await conn.commit()
    return {**state, "run_id": run_id}


async def complete_ai_run(state: ResumeAgentState) -> ResumeAgentState:
    """Graph node: mark ai_runs as completed."""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE ai_runs SET status = 'completed', completed_at = datetime('now') WHERE id = ?",
            (state["run_id"],),
        )
        await conn.commit()
    return state


async def run_pipeline(
    run_id: int,
    job_id: int,
    resume_id: int,
    jd_text: str,
    resume_text: str,
    round_number: int = 0,
    previous_state: dict | None = None,
    conversation_summary: str | None = None,
    recent_messages: list[dict] | None = None,
    needs_jd_analysis: bool = True,
    needs_gap_analysis: bool = True,
    needs_suggestions: bool = True,
    needs_rewrite: bool = True,
    workflow_run_id: str | None = None,
):
    """Execute the resume analysis pipeline.

    Callers pass the four `needs_*` booleans explicitly. For the initial run
    and for retries, all four default to True. For refine follow-ups, callers
    must call `classify_followup` themselves and pass the resulting booleans +
    round_number.
    """
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE ai_runs SET status = 'running' WHERE id = ?", (run_id,)
        )
        await conn.commit()

    workflow_run_id = workflow_run_id or str(uuid.uuid4())

    state = {
        "workflow_run_id": workflow_run_id,
        "job_id": job_id,
        "resume_id": resume_id,
        "run_id": run_id,
        "jd_text": jd_text,
        "resume_text": resume_text,
        "jd_analysis": previous_state.get("jd_analysis") if previous_state else None,
        "rag_chunks": previous_state.get("rag_chunks") if previous_state else None,
        "gap_analysis": previous_state.get("gap_analysis") if previous_state else None,
        "suggestions": previous_state.get("suggestions") if previous_state else None,
        "rewrite": previous_state.get("rewrite") if previous_state else None,
        "conversation_summary": conversation_summary,
        "recent_messages": recent_messages or [],
        "user_preferences": [],
        "needs_jd_analysis": needs_jd_analysis,
        "needs_gap_analysis": needs_gap_analysis,
        "needs_suggestions": needs_suggestions,
        "needs_rewrite": needs_rewrite,
        "round_number": round_number,
    }

    try:
        result = await workflow.ainvoke(state)

        async with get_connection() as conn:
            await conn.execute(
                "UPDATE ai_runs SET status = 'completed', completed_at = datetime('now') WHERE id = ?",
                (run_id,),
            )
            await conn.commit()

        return result

    except Exception as e:
        async with get_connection() as conn:
            await conn.execute(
                "UPDATE ai_runs SET status = 'failed', error = ? WHERE id = ?",
                (_format_pipeline_error(e), run_id),
            )
            await conn.commit()
        raise
