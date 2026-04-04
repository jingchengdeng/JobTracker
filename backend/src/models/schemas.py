from pydantic import BaseModel, Field


class JdAnalysis(BaseModel):
    """Structured output for JD analysis step."""
    title: str = Field(description="Job title")
    company: str = Field(description="Company name")
    key_requirements: list[str] = Field(description="Core requirements from the JD")
    preferred_qualifications: list[str] = Field(description="Nice-to-have qualifications")
    technologies: list[str] = Field(description="Technologies and tools mentioned")
    soft_skills: list[str] = Field(description="Soft skills and traits mentioned")


class GapItem(BaseModel):
    requirement: str = Field(description="The JD requirement")
    status: str = Field(description="match, partial, or gap")
    evidence: str = Field(description="What in the resume matches, or what is missing")
    rag_suggestion: str | None = Field(
        default=None,
        description="Relevant experience from other resumes that could fill this gap",
    )


class GapAnalysis(BaseModel):
    """Structured output for gap analysis step."""
    items: list[GapItem]
    overall_match_score: int = Field(description="0-100 match percentage")
    summary: str = Field(description="Brief summary of the gap analysis")


class SuggestionItem(BaseModel):
    section: str = Field(description="Resume section (summary, experience, skills, etc.)")
    current: str = Field(description="Current content or 'missing'")
    suggested: str = Field(description="Suggested replacement or addition")
    reasoning: str = Field(description="Why this change helps")


class Suggestions(BaseModel):
    """Structured output for suggestions step."""
    items: list[SuggestionItem]


class RewriteResult(BaseModel):
    """Structured output for full rewrite step."""
    rewritten_resume: str = Field(description="The complete rewritten resume text")
    changes_made: list[str] = Field(description="Summary of what was changed and why")


class ClassifierOutput(BaseModel):
    """Structured output for the classifier node."""
    needs_jd_analysis: bool = Field(description="Whether JD analysis needs to re-run")
    needs_gap_analysis: bool = Field(description="Whether gap analysis needs to re-run")
    needs_suggestions: bool = Field(description="Whether suggestions need to re-run")
    needs_rewrite: bool = Field(description="Whether rewrite needs to re-run")
    reasoning: str = Field(description="Why these steps were selected")
