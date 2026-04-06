import pytest
from pydantic import ValidationError


class TestTurnResponse:
    def test_valid_follow_up(self):
        from src.agents.interview_schemas import TurnResponse

        data = {
            "next_action": "follow_up",
            "current_topic_covered": False,
            "next_topic_id": None,
            "interviewer_message": "Can you elaborate on the caching strategy?",
        }
        resp = TurnResponse(**data)
        assert resp.next_action == "follow_up"
        assert resp.interviewer_message.startswith("Can you")

    def test_valid_next_topic(self):
        from src.agents.interview_schemas import TurnResponse

        data = {
            "next_action": "next_topic",
            "current_topic_covered": True,
            "next_topic_id": "behavioral-1",
            "interviewer_message": "Great. Let's move on to a behavioral question.",
        }
        resp = TurnResponse(**data)
        assert resp.current_topic_covered is True
        assert resp.next_topic_id == "behavioral-1"

    def test_valid_close(self):
        from src.agents.interview_schemas import TurnResponse

        data = {
            "next_action": "close",
            "current_topic_covered": True,
            "next_topic_id": None,
            "interviewer_message": "That wraps up our session. Thanks for your time.",
        }
        resp = TurnResponse(**data)
        assert resp.next_action == "close"

    def test_invalid_action_rejected(self):
        from src.agents.interview_schemas import TurnResponse

        with pytest.raises(ValidationError):
            TurnResponse(
                next_action="skip",
                current_topic_covered=False,
                next_topic_id=None,
                interviewer_message="test",
            )

    def test_extra_fields_rejected(self):
        from src.agents.interview_schemas import TurnResponse

        with pytest.raises(ValidationError):
            TurnResponse(
                next_action="follow_up",
                current_topic_covered=False,
                next_topic_id=None,
                interviewer_message="test",
                extra_field="not allowed",
            )


class TestInterviewPlan:
    def test_valid_plan(self):
        from src.agents.interview_schemas import InterviewPlan

        data = {
            "topics": [
                {
                    "id": "sys-1",
                    "area": "System Design",
                    "questions": ["Design a URL shortener"],
                    "rubric": ["Scalability"],
                    "time_allocation_minutes": 10,
                }
            ],
            "opening_prompt": "Tell me about yourself.",
        }
        plan = InterviewPlan(**data)
        assert len(plan.topics) == 1
        assert plan.topics[0].id == "sys-1"


class TestInterviewScore:
    def test_valid_score(self):
        from src.agents.interview_schemas import InterviewScore

        data = {
            "dimension_scores": [
                {"name": "Problem Solving", "score": 8, "feedback": "Good approach",
                 "evidence": "Candidate said: 'I would start by breaking down the problem into subproblems'"},
            ],
            "strengths": ["Clear thinking"],
            "improvements": ["Add error handling discussion"],
            "model_answers": [
                {
                    "question": "How would you handle cache invalidation?",
                    "user_answer_summary": "TTL-based expiry",
                    "model_answer": "Combine TTL with event-driven invalidation.",
                    "gap": "Missing event-driven approach",
                },
            ],
            "summary": "Solid performance overall.",
        }
        score = InterviewScore(**data)
        assert score.dimension_scores[0].score == 8
        assert len(score.model_answers) == 1

    def test_dimension_score_rejects_out_of_range(self):
        from src.agents.interview_schemas import DimensionScore
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DimensionScore(name="X", score=15, feedback="Too high", evidence="None")
        with pytest.raises(ValidationError):
            DimensionScore(name="X", score=-1, feedback="Too low", evidence="None")
