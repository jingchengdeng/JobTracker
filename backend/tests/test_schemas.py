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
