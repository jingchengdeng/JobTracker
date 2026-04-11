from pydantic import BaseModel, Field


class JdAnalysis(BaseModel):
    """Structured analysis of a job description."""
    role_title: str = Field(description="The job title, e.g. 'Senior Software Engineer'")
    role_domain: str = Field(description="Department area, e.g. 'engineering', 'marketing', 'finance'")
    seniority: str = Field(description="Level: 'entry', 'mid', 'senior', 'lead', 'manager', 'director', 'vp', 'c_suite'")
    leadership_titles: list[str] = Field(description="One-level-up titles, e.g. ['Engineering Manager', 'Director of Engineering']")
    department_keywords: list[str] = Field(description="Relevant terms for the role domain, e.g. ['backend', 'infrastructure']")
    domain: str | None = Field(
        default=None,
        description=(
            "Company website domain extracted from the JD text (e.g. 'stripe.com'). "
            "Return null unless an explicit URL, email, or website reference appears in the description."
        ),
    )


class PersonRelevanceScore(BaseModel):
    """Relevance score for a single person."""
    linkedin_url: str
    score: int = Field(ge=0, le=100, description="0-100 relevance to the job")
    reason: str = Field(description="Brief explanation for the score")


class RelevanceScores(BaseModel):
    """Batch of relevance scores."""
    scores: list[PersonRelevanceScore]


class ConnectionNote(BaseModel):
    """Personalized LinkedIn connection note."""
    linkedin_url: str
    note: str = Field(description="Personalized connection note, target 280 characters")


class ConnectionNotes(BaseModel):
    """Batch of connection notes."""
    notes: list[ConnectionNote]


class CompanySummary(BaseModel):
    """Interview-prep-oriented company summary."""
    summary: str = Field(description="2-3 paragraph company summary oriented toward interview preparation")


class LeadershipReview(BaseModel):
    """Review of leadership search results for relevance."""
    relevant_count: int = Field(description="Number of results relevant to the role domain")
    total_count: int = Field(description="Total number of results reviewed")
    needs_retry: bool = Field(description="True if >50% of results are irrelevant")
    refined_query: str | None = Field(default=None, description="Tighter search query if needs_retry is true")
