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


class ResumeAgentState(TypedDict):
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


def _update_step_status(
    run_id: int, step_type: str, status: str, result: str | None = None, round_number: int = 0
):
    """Update or create a step record in the database."""
    conn = get_connection()

    existing = conn.execute(
        "SELECT id, version FROM ai_steps WHERE run_id = ? AND step_type = ? ORDER BY version DESC LIMIT 1",
        (run_id, step_type),
    ).fetchone()

    if existing and status == "running":
        conn.execute(
            "INSERT INTO ai_steps (run_id, step_type, status, version, round_number) "
            "VALUES (?, ?, ?, ?, ?)",
            (run_id, step_type, status, existing["version"] + 1, round_number),
        )
    elif existing:
        # UPDATE targets the latest-version row, which was INSERTed at "running"
        # with the correct round_number. No need to overwrite it here.
        conn.execute(
            "UPDATE ai_steps SET status = ?, result = ?, completed_at = datetime('now') WHERE id = ?",
            (status, result, existing["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO ai_steps (run_id, step_type, status, result, round_number) "
            "VALUES (?, ?, ?, ?, ?)",
            (run_id, step_type, status, result, round_number),
        )

    conn.commit()
    conn.close()


def _wrap_step(step_type: str, step_fn):
    """Wrap a pipeline step to track status in the database."""
    def wrapped(state: ResumeAgentState) -> ResumeAgentState:
        run_id = state["run_id"]
        round_number = state["round_number"]
        _update_step_status(run_id, step_type, "running", round_number=round_number)
        try:
            new_state = step_fn(state)
            result_key = {
                "jd_analysis": "jd_analysis",
                "gap_analysis": "gap_analysis",
                "suggestions": "suggestions",
                "rewrite": "rewrite",
            }.get(step_type, step_type)
            _update_step_status(
                run_id, step_type, "completed",
                result=new_state.get(result_key), round_number=round_number,
            )
            return new_state
        except Exception as e:
            _update_step_status(run_id, step_type, "failed", result=str(e), round_number=round_number)
            raise
    return wrapped


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

    graph.add_node("jd_analysis", _wrap_step("jd_analysis", step_jd_analysis))
    graph.add_node("rag_retrieval", step_rag_retrieval)
    graph.add_node("gap_analysis", _wrap_step("gap_analysis", step_gap_analysis))
    graph.add_node("suggestions", _wrap_step("suggestions", step_suggestions))
    graph.add_node("rewrite", _wrap_step("rewrite", step_rewrite))

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


def _format_pipeline_error(exc: Exception) -> str:
    """Shorten provider errors so the UI doesn't render raw HTML bodies.

    Some providers (e.g. openai-codex -> chatgpt.com) respond with a Cloudflare
    challenge page when the caller isn't authenticated the way they expect. The
    OpenAI SDK includes the response body in the exception string, which then
    leaks into ai_runs.error and the UI. Detect HTML bodies and replace with
    a short, actionable message.
    """
    msg = str(exc)
    lowered = msg.lower()
    if "<html" in lowered or "cloudflare" in lowered or "cf_chl_opt" in lowered:
        return (
            "Provider returned a challenge page instead of an API response. "
            "The configured provider appears to be unreachable from this app. "
            "Switch the default chat provider in Settings to one with a valid API key."
        )
    # Keep errors to a reasonable length in the UI.
    if len(msg) > 500:
        return msg[:500] + "..."
    return msg


def run_pipeline(
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
):
    """Execute the resume analysis pipeline.

    Callers pass the four `needs_*` booleans explicitly. For the initial run
    and for retries, all four default to True. For refine follow-ups, callers
    must call `classify_followup` themselves and pass the resulting booleans +
    round_number.
    """
    conn = get_connection()
    conn.execute(
        "UPDATE ai_runs SET status = 'running' WHERE id = ?", (run_id,)
    )
    conn.commit()
    conn.close()

    state = {
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
        result = workflow.invoke(state)

        conn = get_connection()
        conn.execute(
            "UPDATE ai_runs SET status = 'completed', completed_at = datetime('now') WHERE id = ?",
            (run_id,),
        )
        conn.commit()
        conn.close()

        return result

    except Exception as e:
        conn = get_connection()
        conn.execute(
            "UPDATE ai_runs SET status = 'failed', error = ? WHERE id = ?",
            (_format_pipeline_error(e), run_id),
        )
        conn.commit()
        conn.close()
        raise
