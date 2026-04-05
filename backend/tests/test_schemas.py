import pytest
from pydantic import ValidationError

from src.models.schemas import (
    JdAnalysis,
    GapAnalysis,
    GapItem,
    Suggestions,
    SuggestionItem,
    RewriteResult,
    ClassifierOutput,
)


def test_jd_analysis_schema():
    result = JdAnalysis(
        title="Software Engineer",
        company="Stripe",
        key_requirements=["Python", "distributed systems"],
        preferred_qualifications=["Go experience"],
        technologies=["Python", "Kafka", "PostgreSQL"],
        soft_skills=["leadership"],
    )
    assert result.title == "Software Engineer"
    assert len(result.key_requirements) == 2


def test_gap_analysis_schema():
    item = GapItem(
        requirement="Python",
        status="match",
        evidence="5 years of Python experience listed",
        rag_suggestion=None,
    )
    result = GapAnalysis(items=[item], overall_match_score=85, summary="Strong match")
    assert result.overall_match_score == 85
    assert result.items[0].status == "match"


def test_gap_item_rag_suggestion_is_required():
    # OpenAI strict mode demands every property stay in `required`, even
    # nullable ones. Omitting rag_suggestion must fail.
    with pytest.raises(ValidationError):
        GapItem(requirement="Python", status="match", evidence="5 years")


@pytest.mark.parametrize(
    "cls",
    [JdAnalysis, GapAnalysis, Suggestions, RewriteResult, ClassifierOutput],
)
def test_schema_is_openai_strict_compatible(cls):
    # Every object node in the emitted JSON schema (root + anything in $defs)
    # must have additionalProperties=false and list all properties as required.
    # This is what OpenAI's strict structured-output validator enforces.
    def walk(node, path):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False, (
                    f"{cls.__name__}: additionalProperties not false at {path}"
                )
                props = set(node.get("properties", {}).keys())
                required = set(node.get("required", []))
                assert props == required, (
                    f"{cls.__name__}: missing {props - required} from required at {path}"
                )
            for k, v in node.items():
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(cls.model_json_schema(), cls.__name__)


def test_extra_fields_are_rejected():
    # extra="forbid" must reject unknown keys - this is what emits
    # additionalProperties=false in the generated JSON schema.
    with pytest.raises(ValidationError):
        JdAnalysis(
            title="x",
            company="y",
            key_requirements=[],
            preferred_qualifications=[],
            technologies=[],
            soft_skills=[],
            bogus_field="nope",
        )


def test_classifier_output_schema():
    result = ClassifierOutput(
        needs_jd_analysis=False,
        needs_gap_analysis=False,
        needs_suggestions=False,
        needs_rewrite=True,
        reasoning="User asked for shorter text, only rewrite needed",
    )
    assert result.needs_rewrite is True
    assert result.needs_jd_analysis is False
