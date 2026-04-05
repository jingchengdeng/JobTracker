from src.models.schemas import ClassifierOutput


def test_classifier_output_rewrite_only():
    """Test that ClassifierOutput can represent rewrite-only routing."""
    output = ClassifierOutput(
        needs_jd_analysis=False,
        needs_gap_analysis=False,
        needs_suggestions=False,
        needs_rewrite=True,
        reasoning="User asked for formatting change",
        response_message="Sure, I'll apply the formatting change.",
    )
    assert output.needs_rewrite is True
    assert output.needs_jd_analysis is False


def test_classifier_output_full_rerun():
    """Test that ClassifierOutput can represent full pipeline re-run."""
    output = ClassifierOutput(
        needs_jd_analysis=True,
        needs_gap_analysis=True,
        needs_suggestions=True,
        needs_rewrite=True,
        reasoning="New JD information provided",
        response_message="Got it — I'll rerun the full pipeline with the new JD.",
    )
    assert all([
        output.needs_jd_analysis,
        output.needs_gap_analysis,
        output.needs_suggestions,
        output.needs_rewrite,
    ])
