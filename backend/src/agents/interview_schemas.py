from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


_STRICT = ConfigDict(extra="forbid")


class TurnResponse(BaseModel):
    model_config = _STRICT

    next_action: Literal["follow_up", "next_topic", "close"]
    current_topic_covered: bool
    next_topic_id: str | None
    interviewer_message: str


class TopicPlan(BaseModel):
    model_config = _STRICT

    id: str
    area: str
    questions: list[str]
    rubric: list[str]
    time_allocation_minutes: int


class InterviewPlan(BaseModel):
    model_config = _STRICT

    topics: list[TopicPlan]
    opening_prompt: str


class ModelAnswer(BaseModel):
    model_config = _STRICT

    question: str
    user_answer_summary: str
    model_answer: str
    gap: str


class DimensionScore(BaseModel):
    model_config = _STRICT

    name: str
    score: int = Field(ge=0, le=10)
    feedback: str
    evidence: str


class InterviewScore(BaseModel):
    model_config = _STRICT

    dimension_scores: list[DimensionScore]
    strengths: list[str]
    improvements: list[str]
    model_answers: list[ModelAnswer]
    summary: str
