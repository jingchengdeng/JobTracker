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
    ]
    if session.get("focus_area"):
        parts.append(f"Focus area: {session['focus_area']}.")
    if preferences:
        parts.append("\nCandidate preferences:")
        for pref in preferences:
            parts.append(f"- {pref}")
    return "\n".join(parts)


def run_planning(session_id: int) -> None:
    session = load_session(session_id)
    llm = get_interview_model()
    structured_llm = llm.with_structured_output(InterviewPlan)
    preferences = load_all_preferences()

    from src.db import get_connection
    conn = get_connection()
    job = conn.execute("SELECT description FROM jobs WHERE id = ?", (session["job_id"],)).fetchone()
    resume = conn.execute(
        "SELECT extracted_text FROM resumes WHERE id = ?", (session["resume_id"],)
    ).fetchone() if session["resume_id"] else None
    conn.close()

    jd_text = job["description"] if job else ""
    resume_text = resume["extracted_text"] if resume else ""

    system = _build_system_prompt(session, preferences)
    prompt = (
        f"Create an interview plan for this candidate.\n\n"
        f"Job Description:\n{jd_text}\n\n"
        f"Candidate Resume:\n{resume_text}\n\n"
        f"Generate {session['duration_minutes'] // 5} questions across relevant topics. "
        f"Include a rubric for each topic and derive 3-5 scoring dimensions from the JD."
    )

    plan = structured_llm.invoke([
        SystemMessage(content=system),
        HumanMessage(content=prompt),
    ])

    save_plan(
        session_id,
        plan.model_dump(exclude={"scoring_dimensions"}),
        [d.model_dump() for d in plan.scoring_dimensions],
    )
    save_turn(session_id, "interviewer", plan.opening_prompt)
    update_session_status(session_id, "active")


def process_interview_turn(session_id: int, transcript: str) -> TurnResponse:
    session = load_session(session_id)
    plan, scoring_dims = load_plan(session_id)
    turns = load_turns(session_id)
    preferences = load_all_preferences()

    save_turn(session_id, "candidate", transcript)

    llm = get_interview_model()
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
        f"You are conducting an interview. Here is the conversation so far:\n\n"
        f"{history}\n\n"
        f"Interview plan:\n{_format_plan(plan)}\n\n"
        f"Current topic: {current_topic['area'] if current_topic else 'none remaining'}\n"
        f"Topics remaining: {len(uncovered)}\n\n"
        f"Evaluate the candidate's last answer and decide what to do next. "
        f"If the answer was weak, follow up to probe deeper. "
        f"If the answer was strong and the topic is covered, move to the next topic. "
        f"If all topics are covered or time is up, close the interview."
    )

    try:
        structured_llm = llm.with_structured_output(TurnResponse)
        turn_response = structured_llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=prompt),
        ])
    except (ValidationError, Exception) as exc:
        logger.warning("Structured output failed, using fallback: %s", exc)
        fallback = llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=(
                f"{history}\n\nAsk the next interview question. "
                f"Just respond with the question, nothing else."
            )),
        ])
        turn_response = TurnResponse(
            next_action="follow_up",
            current_topic_covered=False,
            next_topic_id=None,
            interviewer_message=fallback.content if isinstance(fallback.content, str) else str(fallback.content),
        )

    topic_ref = current_topic["id"] if current_topic else None
    save_turn(session_id, "interviewer", turn_response.interviewer_message, plan_topic_ref=topic_ref)

    return turn_response


def run_scoring(session_id: int) -> None:
    session = load_session(session_id)
    plan, scoring_dims = load_plan(session_id)
    turns = load_turns(session_id)

    llm = get_interview_model()
    structured_llm = llm.with_structured_output(InterviewScore)

    history = "\n".join(
        f"{'Interviewer' if t['role'] == 'interviewer' else 'Candidate'}: {t['text']}"
        for t in turns
    )

    system = (
        "You are an expert interview evaluator. Score the candidate's performance "
        "based on the interview transcript, the original plan, and the scoring dimensions."
    )
    prompt = (
        f"Interview transcript:\n{history}\n\n"
        f"Interview plan:\n{_format_plan(plan)}\n\n"
        f"Scoring dimensions:\n{_format_dimensions(scoring_dims)}\n\n"
        f"Produce an overall score (0-100), per-dimension scores with feedback, "
        f"a list of strengths, areas for improvement, and model answers for any "
        f"questions where the candidate's answer was weak or incorrect."
    )

    score = structured_llm.invoke([
        SystemMessage(content=system),
        HumanMessage(content=prompt),
    ])

    save_results(session_id, score.model_dump())
    update_session_status(session_id, "completed")


def _format_plan(plan: dict) -> str:
    lines = []
    for topic in plan.get("topics", []):
        lines.append(f"- {topic['area']}: {', '.join(topic['questions'][:2])}")
    return "\n".join(lines)


def _format_dimensions(dims: list[dict]) -> str:
    return "\n".join(f"- {d['name']} (weight: {d['weight']}): {d['description']}" for d in dims)
