import asyncio
import logging

from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import ValidationError

from src.agents.interview_schemas import InterviewPlan, TurnResponse, InterviewScore
from src.agents.interview_db import (
    load_session, load_plan, load_turns, save_plan, save_turn,
    save_results, update_session_status,
)
from src.models.provider import get_interview_model
from src.memory.preferences import load_all_preferences

logger = logging.getLogger(__name__)


def _build_system_prompt(session: dict, preferences: list[str]) -> str:
    parts = [
        f"You are an expert interviewer conducting a {session['interview_type']} interview. "
        f"Difficulty: {session['difficulty']}. Target duration: {session['duration_minutes']} minutes.",
        "",
        "Rules:",
        "- Ask ONE question at a time. Never ask multiple questions in a single turn.",
        "- Briefly acknowledge the candidate's answer before asking your next question. Be conversational, not robotic.",
        "- If the candidate's answer is vague or surface-level, probe deeper on the same topic.",
        "- If the answer demonstrates solid understanding, move to the next topic.",
    ]
    if session.get("focus_area"):
        parts.append(f"\nFocus area: {session['focus_area']}.")
    if preferences:
        parts.append("\nCandidate preferences:")
        for pref in preferences:
            parts.append(f"- {pref}")
    return "\n".join(parts)


async def run_planning(session_id: int) -> None:
    session = await load_session(session_id)
    llm = await asyncio.to_thread(get_interview_model)
    structured_llm = llm.with_structured_output(InterviewPlan, method="function_calling")
    preferences = await load_all_preferences()

    from src.db import get_connection
    async with get_connection() as conn:
        cursor = await conn.execute("SELECT description FROM jobs WHERE id = ?", (session["job_id"],))
        job = await cursor.fetchone()
        if session["resume_id"]:
            cursor = await conn.execute(
                "SELECT extracted_text FROM resumes WHERE id = ?", (session["resume_id"],)
            )
            resume = await cursor.fetchone()
        else:
            resume = None

    jd_text = job["description"] if job else ""
    resume_text = resume["extracted_text"] if resume else ""

    system = _build_system_prompt(session, preferences)
    prompt = (
        f"Create an interview plan for this candidate.\n\n"
        f"Job Description:\n{jd_text}\n\n"
        f"Candidate Resume:\n{resume_text}\n\n"
        f"Generate topics to cover in {session['duration_minutes']} minutes. "
        f"For each topic, list suggested angles to explore and a rubric for evaluation. "
        f"The opening_prompt should be a single conversational question to start the interview."
    )

    plan = await structured_llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=prompt),
    ])

    await save_plan(session_id, plan.model_dump())
    await save_turn(session_id, "interviewer", plan.opening_prompt)
    await update_session_status(session_id, "active")


async def process_interview_turn(session_id: int, transcript: str) -> TurnResponse:
    session = await load_session(session_id)
    plan = await load_plan(session_id)
    turns = await load_turns(session_id)
    preferences = await load_all_preferences()

    await save_turn(session_id, "candidate", transcript)

    llm = await asyncio.to_thread(get_interview_model)
    system = _build_system_prompt(session, preferences)

    history = "\n".join(
        f"{'Interviewer' if t['role'] == 'interviewer' else 'Candidate'}: {t['text']}"
        for t in turns
    )
    history += f"\nCandidate: {transcript}"

    covered_refs = {t["plan_topic_ref"] for t in turns if t.get("plan_topic_ref")}
    uncovered = [t for t in plan.get("topics", []) if t["id"] not in covered_refs]
    current_topic = uncovered[0] if uncovered else None

    prompt = (
        f"Conversation so far:\n\n{history}\n\n"
        f"Interview plan:\n{_format_plan(plan)}\n\n"
        f"Current topic: {current_topic['area'] if current_topic else 'none remaining'}\n"
        f"Topics remaining: {len(uncovered)}\n\n"
        f"The candidate just answered. Briefly acknowledge their answer, "
        f"then ask ONE follow-up or move to the next topic. "
        f"If all topics are covered or time is up, close the interview."
    )

    try:
        structured_llm = llm.with_structured_output(TurnResponse, method="function_calling")
        turn_response = await structured_llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=prompt),
        ])
    except (ValidationError, Exception) as exc:
        logger.warning("Structured output failed, using fallback: %s", exc)
        fallback = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=(
                f"{history}\n\nBriefly acknowledge the candidate's last answer, "
                f"then ask ONE follow-up question."
            )),
        ])
        turn_response = TurnResponse(
            next_action="follow_up",
            current_topic_covered=False,
            next_topic_id=None,
            interviewer_message=fallback.content if isinstance(fallback.content, str) else str(fallback.content),
        )

    topic_ref = current_topic["id"] if current_topic else None
    await save_turn(session_id, "interviewer", turn_response.interviewer_message, plan_topic_ref=topic_ref)

    return turn_response


async def run_scoring(session_id: int) -> None:
    session = await load_session(session_id)
    plan = await load_plan(session_id)
    turns = await load_turns(session_id)

    from src.agents.interview_config import SCORING_DIMENSIONS
    dimensions = SCORING_DIMENSIONS.get(session["interview_type"], SCORING_DIMENSIONS["technical"])

    llm = await asyncio.to_thread(get_interview_model)
    structured_llm = llm.with_structured_output(InterviewScore, method="function_calling")

    history = "\n".join(
        f"{'Interviewer' if t['role'] == 'interviewer' else 'Candidate'}: {t['text']}"
        for t in turns
    )

    dim_text = "\n".join(
        f"- {d['name']}: {d['description']}" for d in dimensions
    )

    system = (
        "You are an expert interview evaluator. Score the candidate's performance "
        "based on the interview transcript and the scoring dimensions below.\n\n"
        "Scoring scale for EACH dimension: 0-10\n"
        "  0 = no evidence\n"
        "  3 = weak with major gaps\n"
        "  5 = adequate\n"
        "  7 = solid with minor gaps\n"
        "  10 = exceptional with specific evidence\n\n"
        "For each dimension, you MUST cite a specific quote from the transcript "
        "in the 'evidence' field that justifies your score. If there is no relevant "
        "quote, state 'No evidence in transcript' and score 0."
    )
    prompt = (
        f"Interview transcript:\n{history}\n\n"
        f"Interview plan:\n{_format_plan(plan)}\n\n"
        f"Score EXACTLY these {len(dimensions)} dimensions (one score per dimension, use these exact names):\n{dim_text}\n\n"
        f"Produce per-dimension scores with feedback and evidence, "
        f"a list of strengths, areas for improvement, and model answers for any "
        f"questions where the candidate's answer was weak or incorrect."
    )

    score = await structured_llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=prompt),
    ])

    await save_results(session_id, score.model_dump())
    await update_session_status(session_id, "completed")


def _format_plan(plan: dict) -> str:
    lines = []
    for topic in plan.get("topics", []):
        lines.append(f"- {topic['area']}: {', '.join(topic['questions'][:2])}")
    return "\n".join(lines)
