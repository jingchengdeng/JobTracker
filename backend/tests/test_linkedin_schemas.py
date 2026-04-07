import pytest
from pydantic import ValidationError


class TestJdAnalysis:
    def test_valid_construction(self):
        from src.agents.linkedin_schemas import JdAnalysis

        jd = JdAnalysis(
            role_title="Senior Software Engineer",
            role_domain="engineering",
            seniority="senior",
            leadership_titles=["Engineering Manager", "Director of Engineering"],
            department_keywords=["backend", "infrastructure"],
        )
        assert jd.role_title == "Senior Software Engineer"
        assert jd.seniority == "senior"
        assert len(jd.leadership_titles) == 2
        assert "backend" in jd.department_keywords

    def test_empty_leadership_titles_allowed(self):
        from src.agents.linkedin_schemas import JdAnalysis

        jd = JdAnalysis(
            role_title="Marketing Analyst",
            role_domain="marketing",
            seniority="mid",
            leadership_titles=[],
            department_keywords=["brand", "growth"],
        )
        assert jd.leadership_titles == []

    def test_empty_department_keywords_allowed(self):
        from src.agents.linkedin_schemas import JdAnalysis

        jd = JdAnalysis(
            role_title="Product Manager",
            role_domain="product",
            seniority="lead",
            leadership_titles=["VP of Product"],
            department_keywords=[],
        )
        assert jd.department_keywords == []


class TestPersonRelevanceScore:
    def test_valid_construction(self):
        from src.agents.linkedin_schemas import PersonRelevanceScore

        p = PersonRelevanceScore(
            linkedin_url="https://www.linkedin.com/in/jane-doe",
            score=85,
            reason="Hiring manager for the relevant team.",
        )
        assert p.score == 85
        assert "jane-doe" in p.linkedin_url

    def test_score_boundary_zero(self):
        from src.agents.linkedin_schemas import PersonRelevanceScore

        p = PersonRelevanceScore(
            linkedin_url="https://www.linkedin.com/in/someone",
            score=0,
            reason="Completely unrelated role.",
        )
        assert p.score == 0

    def test_score_boundary_hundred(self):
        from src.agents.linkedin_schemas import PersonRelevanceScore

        p = PersonRelevanceScore(
            linkedin_url="https://www.linkedin.com/in/someone",
            score=100,
            reason="Direct hiring manager.",
        )
        assert p.score == 100

    def test_score_above_max_rejected(self):
        from src.agents.linkedin_schemas import PersonRelevanceScore

        with pytest.raises(ValidationError):
            PersonRelevanceScore(
                linkedin_url="https://www.linkedin.com/in/someone",
                score=150,
                reason="Out of range.",
            )

    def test_score_below_min_rejected(self):
        from src.agents.linkedin_schemas import PersonRelevanceScore

        with pytest.raises(ValidationError):
            PersonRelevanceScore(
                linkedin_url="https://www.linkedin.com/in/someone",
                score=-1,
                reason="Negative score.",
            )


class TestRelevanceScores:
    def test_valid_batch(self):
        from src.agents.linkedin_schemas import RelevanceScores

        batch = RelevanceScores(
            scores=[
                {
                    "linkedin_url": "https://www.linkedin.com/in/alice",
                    "score": 90,
                    "reason": "Senior engineer on the relevant team.",
                },
                {
                    "linkedin_url": "https://www.linkedin.com/in/bob",
                    "score": 40,
                    "reason": "Different department.",
                },
            ]
        )
        assert len(batch.scores) == 2
        assert batch.scores[0].score == 90

    def test_empty_scores_allowed(self):
        from src.agents.linkedin_schemas import RelevanceScores

        batch = RelevanceScores(scores=[])
        assert batch.scores == []


class TestConnectionNote:
    def test_valid_construction(self):
        from src.agents.linkedin_schemas import ConnectionNote

        note = ConnectionNote(
            linkedin_url="https://www.linkedin.com/in/carol",
            note="Hi Carol, I noticed your work on distributed systems at Acme and would love to connect.",
        )
        assert "Carol" in note.note

    def test_note_up_to_300_chars(self):
        from src.agents.linkedin_schemas import ConnectionNote

        long_note = "A" * 300
        note = ConnectionNote(
            linkedin_url="https://www.linkedin.com/in/dave",
            note=long_note,
        )
        assert len(note.note) == 300


class TestConnectionNotes:
    def test_valid_batch(self):
        from src.agents.linkedin_schemas import ConnectionNotes

        batch = ConnectionNotes(
            notes=[
                {
                    "linkedin_url": "https://www.linkedin.com/in/eve",
                    "note": "Hi Eve, I'm applying for the backend role and would love to connect.",
                },
            ]
        )
        assert len(batch.notes) == 1
        assert "Eve" in batch.notes[0].note

    def test_empty_notes_allowed(self):
        from src.agents.linkedin_schemas import ConnectionNotes

        batch = ConnectionNotes(notes=[])
        assert batch.notes == []


class TestCompanySummary:
    def test_valid_construction(self):
        from src.agents.linkedin_schemas import CompanySummary

        summary = CompanySummary(
            summary=(
                "Acme Corp is a cloud-infrastructure company founded in 2010. "
                "It is known for its reliability tooling used by Fortune 500 companies. "
                "Going into an interview, candidates should highlight experience with high-availability systems."
            )
        )
        assert "Acme Corp" in summary.summary

    def test_multiline_summary(self):
        from src.agents.linkedin_schemas import CompanySummary

        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        s = CompanySummary(summary=text)
        assert s.summary == text


class TestLeadershipReview:
    def test_valid_no_retry(self):
        from src.agents.linkedin_schemas import LeadershipReview

        review = LeadershipReview(
            relevant_count=8,
            total_count=10,
            needs_retry=False,
            refined_query=None,
        )
        assert review.relevant_count == 8
        assert review.needs_retry is False
        assert review.refined_query is None

    def test_valid_needs_retry_with_refined_query(self):
        from src.agents.linkedin_schemas import LeadershipReview

        review = LeadershipReview(
            relevant_count=3,
            total_count=10,
            needs_retry=True,
            refined_query="Engineering Manager backend infrastructure",
        )
        assert review.needs_retry is True
        assert review.refined_query == "Engineering Manager backend infrastructure"

    def test_refined_query_defaults_to_none(self):
        from src.agents.linkedin_schemas import LeadershipReview

        review = LeadershipReview(
            relevant_count=5,
            total_count=10,
            needs_retry=False,
        )
        assert review.refined_query is None
