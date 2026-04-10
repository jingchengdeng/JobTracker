from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator


VALID_WORK_MODES = {"remote", "hybrid", "onsite"}
VALID_JOB_TYPES = {"full_time", "part_time", "contract", "internship"}


class LinkedInJobExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(description="Job title")
    company: str = Field(description="Company name")
    location: str | None = Field(default=None, description="City, State or country")
    description: str = Field(description="Full job description text")
    salary_min: int | None = Field(default=None, description="Minimum annual salary as integer, e.g. 130000")
    salary_max: int | None = Field(default=None, description="Maximum annual salary as integer, e.g. 170000")
    salary_currency: str | None = Field(default=None, description="Currency code, e.g. USD")
    job_type: str | None = Field(default=None, description="One of: full_time, part_time, contract, internship")
    work_mode: str | None = Field(default=None, description="One of: remote, hybrid, onsite")

    @field_validator("title", "company", "description")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


class ExtractionState(TypedDict):
    raw_text: str
    url: str
    extracted: dict | None
    validation_errors: list[str]
    retry_count: int
    job_id: int | None
    error: str | None
    workflow_run_id: str


def validate_extraction(data: LinkedInJobExtraction) -> list[str]:
    errors: list[str] = []

    # Required fields
    if not data.title or not data.title.strip():
        errors.append("title is required and must not be empty")
    if not data.company or not data.company.strip():
        errors.append("company is required and must not be empty")
    if not data.description or not data.description.strip():
        errors.append("description is required and must not be empty")

    # Enum validation
    if data.work_mode is not None and data.work_mode not in VALID_WORK_MODES:
        errors.append(
            f"work_mode '{data.work_mode}' is not valid, must be one of: {', '.join(sorted(VALID_WORK_MODES))}"
        )
    if data.job_type is not None and data.job_type not in VALID_JOB_TYPES:
        errors.append(
            f"job_type '{data.job_type}' is not valid, must be one of: {', '.join(sorted(VALID_JOB_TYPES))}"
        )

    # Salary logic
    has_min = data.salary_min is not None
    has_max = data.salary_max is not None
    has_currency = data.salary_currency is not None

    if has_min != has_max:
        errors.append("salary_min and salary_max must both be present or both be null")
    if has_min and data.salary_min <= 0:
        errors.append(f"salary_min ({data.salary_min}) must be a positive integer")
    if has_max and data.salary_max <= 0:
        errors.append(f"salary_max ({data.salary_max}) must be a positive integer")
    if has_min and has_max and data.salary_min > data.salary_max:
        errors.append(f"salary_min ({data.salary_min}) must be <= salary_max ({data.salary_max})")
    if (has_min or has_max) and not has_currency:
        errors.append("salary_currency is required when salary values are present")

    return errors
