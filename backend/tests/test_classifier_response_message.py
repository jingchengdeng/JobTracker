import pytest
from pydantic import ValidationError

from src.models.schemas import ClassifierOutput


def test_classifier_output_has_response_message_field():
    out = ClassifierOutput(
        needs_jd_analysis=False,
        needs_gap_analysis=True,
        needs_suggestions=True,
        needs_rewrite=True,
        reasoning="User wants leadership focus",
        response_message="Sure, I'll refresh the gap analysis and rewrite.",
    )
    assert out.response_message == "Sure, I'll refresh the gap analysis and rewrite."


def test_classifier_output_rejects_missing_response_message():
    with pytest.raises(ValidationError):
        ClassifierOutput(
            needs_jd_analysis=False,
            needs_gap_analysis=True,
            needs_suggestions=True,
            needs_rewrite=True,
            reasoning="x",
        )
