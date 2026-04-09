import pytest
from pydantic import ValidationError


def _valid_data(**overrides):
    base = {
        "title": "Software Engineer",
        "company": "Acme Corp",
        "location": "San Francisco, CA",
        "description": "Build and maintain backend services.",
        "salary_min": 130000,
        "salary_max": 170000,
        "salary_currency": "USD",
        "job_type": "full_time",
        "work_mode": "remote",
    }
    base.update(overrides)
    return base


class TestLinkedInJobExtraction:
    def test_valid_full(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction

        job = LinkedInJobExtraction(**_valid_data())
        assert job.title == "Software Engineer"
        assert job.company == "Acme Corp"
        assert job.salary_min == 130000
        assert job.work_mode == "remote"

    def test_valid_minimal(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction

        job = LinkedInJobExtraction(
            title="Analyst",
            company="Big Co",
            description="Do analysis work.",
        )
        assert job.location is None
        assert job.salary_min is None
        assert job.job_type is None

    def test_blank_title_rejected(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction

        with pytest.raises(ValidationError):
            LinkedInJobExtraction(**_valid_data(title=""))

    def test_whitespace_title_rejected(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction

        with pytest.raises(ValidationError):
            LinkedInJobExtraction(**_valid_data(title="   "))

    def test_blank_company_rejected(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction

        with pytest.raises(ValidationError):
            LinkedInJobExtraction(**_valid_data(company=""))

    def test_whitespace_company_rejected(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction

        with pytest.raises(ValidationError):
            LinkedInJobExtraction(**_valid_data(company="  "))

    def test_title_and_company_are_stripped(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction

        job = LinkedInJobExtraction(**_valid_data(title="  Engineer  ", company=" Acme "))
        assert job.title == "Engineer"
        assert job.company == "Acme"


class TestValidateExtraction:
    def test_valid_returns_no_errors(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction, validate_extraction

        job = LinkedInJobExtraction(**_valid_data())
        assert validate_extraction(job) == []

    def test_valid_minimal_returns_no_errors(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction, validate_extraction

        job = LinkedInJobExtraction(
            title="Analyst",
            company="Big Co",
            description="Do analysis work.",
        )
        assert validate_extraction(job) == []

    def test_empty_title_returns_error(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction, validate_extraction

        # Use model_construct to bypass Pydantic validator so we can test validate_extraction directly
        job = LinkedInJobExtraction.model_construct(
            title="",
            company="Acme",
            description="Some description",
        )
        errors = validate_extraction(job)
        assert any("title" in e for e in errors)

    def test_empty_company_returns_error(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction, validate_extraction

        job = LinkedInJobExtraction.model_construct(
            title="Engineer",
            company="",
            description="Some description",
        )
        errors = validate_extraction(job)
        assert any("company" in e for e in errors)

    def test_empty_description_returns_error(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction, validate_extraction

        job = LinkedInJobExtraction.model_construct(
            title="Engineer",
            company="Acme",
            description="",
        )
        errors = validate_extraction(job)
        assert any("description" in e for e in errors)

    def test_invalid_work_mode_returns_error(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction, validate_extraction

        job = LinkedInJobExtraction.model_construct(
            title="Engineer",
            company="Acme",
            description="Description here",
            work_mode="flexible",
        )
        errors = validate_extraction(job)
        assert any("work_mode" in e for e in errors)

    def test_invalid_job_type_returns_error(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction, validate_extraction

        job = LinkedInJobExtraction.model_construct(
            title="Engineer",
            company="Acme",
            description="Description here",
            job_type="freelance",
        )
        errors = validate_extraction(job)
        assert any("job_type" in e for e in errors)

    def test_salary_min_greater_than_max_returns_error(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction, validate_extraction

        job = LinkedInJobExtraction.model_construct(
            title="Engineer",
            company="Acme",
            description="Description here",
            salary_min=200000,
            salary_max=150000,
            salary_currency="USD",
        )
        errors = validate_extraction(job)
        assert any("salary_min" in e and "salary_max" in e for e in errors)

    def test_salary_min_without_max_returns_error(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction, validate_extraction

        job = LinkedInJobExtraction.model_construct(
            title="Engineer",
            company="Acme",
            description="Description here",
            salary_min=130000,
            salary_max=None,
            salary_currency="USD",
        )
        errors = validate_extraction(job)
        assert any("salary_min" in e and "salary_max" in e for e in errors)

    def test_salary_max_without_min_returns_error(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction, validate_extraction

        job = LinkedInJobExtraction.model_construct(
            title="Engineer",
            company="Acme",
            description="Description here",
            salary_min=None,
            salary_max=170000,
            salary_currency="USD",
        )
        errors = validate_extraction(job)
        assert any("salary_min" in e and "salary_max" in e for e in errors)

    def test_salary_without_currency_returns_error(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction, validate_extraction

        job = LinkedInJobExtraction.model_construct(
            title="Engineer",
            company="Acme",
            description="Description here",
            salary_min=130000,
            salary_max=170000,
            salary_currency=None,
        )
        errors = validate_extraction(job)
        assert any("salary_currency" in e for e in errors)

    def test_negative_salary_min_returns_error(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction, validate_extraction

        job = LinkedInJobExtraction.model_construct(
            title="Engineer",
            company="Acme",
            description="Description here",
            salary_min=-1000,
            salary_max=170000,
            salary_currency="USD",
        )
        errors = validate_extraction(job)
        assert any("salary_min" in e for e in errors)

    def test_negative_salary_max_returns_error(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction, validate_extraction

        job = LinkedInJobExtraction.model_construct(
            title="Engineer",
            company="Acme",
            description="Description here",
            salary_min=130000,
            salary_max=-500,
            salary_currency="USD",
        )
        errors = validate_extraction(job)
        assert any("salary_max" in e for e in errors)

    def test_null_salary_fields_pass(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction, validate_extraction

        job = LinkedInJobExtraction.model_construct(
            title="Engineer",
            company="Acme",
            description="Description here",
            salary_min=None,
            salary_max=None,
            salary_currency=None,
        )
        errors = validate_extraction(job)
        assert errors == []

    def test_all_valid_work_modes_pass(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction, validate_extraction, VALID_WORK_MODES

        for mode in VALID_WORK_MODES:
            job = LinkedInJobExtraction.model_construct(
                title="Engineer",
                company="Acme",
                description="Description here",
                work_mode=mode,
            )
            errors = validate_extraction(job)
            assert not any("work_mode" in e for e in errors), f"Unexpected error for work_mode={mode}"

    def test_all_valid_job_types_pass(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction, validate_extraction, VALID_JOB_TYPES

        for jt in VALID_JOB_TYPES:
            job = LinkedInJobExtraction.model_construct(
                title="Engineer",
                company="Acme",
                description="Description here",
                job_type=jt,
            )
            errors = validate_extraction(job)
            assert not any("job_type" in e for e in errors), f"Unexpected error for job_type={jt}"

    def test_zero_salary_min_returns_error(self):
        from src.agents.extraction_schemas import LinkedInJobExtraction, validate_extraction

        job = LinkedInJobExtraction.model_construct(
            title="Engineer",
            company="Acme",
            description="Description here",
            salary_min=0,
            salary_max=170000,
            salary_currency="USD",
        )
        errors = validate_extraction(job)
        assert any("salary_min" in e for e in errors)
