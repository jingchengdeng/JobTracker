import json
import sqlite3
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

from tests.test_interview_db import _create_tables


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    _create_tables(db_path)
    # Add user_preferences table so load_all_preferences doesn't blow up
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE user_preferences "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("JOBTRACKER_DB_PATH", db_path)
    return db_path


def _mock_plan_response():
    from src.agents.interview_schemas import InterviewPlan, TopicPlan

    return InterviewPlan(
        topics=[TopicPlan(
            id="sys-1", area="System Design",
            questions=["Design a URL shortener"],
            rubric=["Scalability"], time_allocation_minutes=10,
        )],
        opening_prompt="Tell me about yourself.",
    )


def _mock_turn_response(action="follow_up", message="Tell me more."):
    from src.agents.interview_schemas import TurnResponse

    return TurnResponse(
        next_action=action,
        current_topic_covered=action == "next_topic",
        next_topic_id="sys-1" if action == "next_topic" else None,
        interviewer_message=message,
    )


def _mock_score_response():
    from src.agents.interview_schemas import InterviewScore, DimensionScore, ModelAnswer

    return InterviewScore(
        dimension_scores=[DimensionScore(
            name="Problem Solving", score=8, feedback="Good",
            evidence="Candidate said: 'I would use a hash-based approach'",
        )],
        strengths=["Clear communication"],
        improvements=["Discuss failure modes"],
        model_answers=[ModelAnswer(
            question="Design X", user_answer_summary="Basic approach",
            model_answer="Better approach", gap="Missing failure modes",
        )],
        summary="Solid performance.",
    )


class TestRunPlanning:
    @patch("src.agents.interview_engine.get_interview_model")
    async def test_creates_plan_and_opening_turn(self, mock_get_model, test_db):
        from src.agents.interview_engine import run_planning
        from src.agents.interview_db import create_session, load_plan, load_turns, load_session

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=_mock_plan_response())
        mock_llm.with_structured_output.return_value = mock_structured
        mock_get_model.return_value = mock_llm

        session_id = await create_session(
            job_id=1, resume_id=1, interview_type="technical",
            difficulty="medium", duration_minutes=30, voice="nova",
        )
        await run_planning(session_id)

        plan = await load_plan(session_id)
        assert len(plan["topics"]) == 1

        turns = await load_turns(session_id)
        assert len(turns) == 1
        assert turns[0]["role"] == "interviewer"
        assert "Tell me about yourself" in turns[0]["text"]

        session = await load_session(session_id)
        assert session["status"] == "active"


class TestProcessInterviewTurn:
    @patch("src.agents.interview_engine.get_interview_model")
    async def test_saves_both_turns_and_returns_response(self, mock_get_model, test_db):
        from src.agents.interview_engine import run_planning, process_interview_turn
        from src.agents.interview_db import create_session, load_turns

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(side_effect=[_mock_plan_response(), _mock_turn_response()])
        mock_llm.with_structured_output.return_value = mock_structured
        mock_get_model.return_value = mock_llm

        session_id = await create_session(
            job_id=1, resume_id=1, interview_type="technical",
            difficulty="medium", duration_minutes=30, voice="nova",
        )
        await run_planning(session_id)

        result = await process_interview_turn(session_id, "I would use a hash-based approach.")

        assert result.next_action == "follow_up"
        assert result.interviewer_message == "Tell me more."

        turns = await load_turns(session_id)
        assert len(turns) == 3  # opening + candidate + interviewer
        assert turns[1]["role"] == "candidate"
        assert turns[2]["role"] == "interviewer"

    @patch("src.agents.interview_engine.get_interview_model")
    async def test_fallback_on_structured_output_failure(self, mock_get_model, test_db):
        from src.agents.interview_engine import run_planning, process_interview_turn
        from src.agents.interview_db import create_session
        from pydantic import ValidationError

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_plain = MagicMock()

        # First call: planning succeeds
        # Second call: structured output fails, plain fallback succeeds
        mock_llm.with_structured_output.return_value = mock_structured
        mock_structured.ainvoke = AsyncMock(side_effect=[
            _mock_plan_response(),
            ValidationError.from_exception_data("TurnResponse", []),
        ])
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Could you tell me more about that?"))
        mock_get_model.return_value = mock_llm

        session_id = await create_session(
            job_id=1, resume_id=1, interview_type="technical",
            difficulty="medium", duration_minutes=30, voice="nova",
        )
        await run_planning(session_id)
        result = await process_interview_turn(session_id, "Some answer.")

        assert result.next_action == "follow_up"
        assert "Could you tell me more" in result.interviewer_message


class TestRunScoring:
    @patch("src.agents.interview_engine.get_interview_model")
    async def test_produces_results_and_completes_session(self, mock_get_model, test_db):
        from src.agents.interview_engine import run_planning, process_interview_turn, run_scoring
        from src.agents.interview_db import create_session, load_results, load_session

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(side_effect=[
            _mock_plan_response(),
            _mock_turn_response(action="close", message="Thanks for your time."),
            _mock_score_response(),
        ])
        mock_llm.with_structured_output.return_value = mock_structured
        mock_get_model.return_value = mock_llm

        session_id = await create_session(
            job_id=1, resume_id=1, interview_type="technical",
            difficulty="medium", duration_minutes=30, voice="nova",
        )
        await run_planning(session_id)
        await process_interview_turn(session_id, "My answer.")
        await run_scoring(session_id)

        results = await load_results(session_id)
        assert results is not None
        assert results["overall_score"] == 8  # sum of dimension scores

        session = await load_session(session_id)
        assert session["status"] == "completed"
