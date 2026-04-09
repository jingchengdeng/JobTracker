import logging

import httpx
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)

from src.models.provider import get_linkedin_model
from src.agents.extraction_schemas import (
    LinkedInJobExtraction,
    ExtractionState,
    validate_extraction,
)

NEXTJS_JOBS_URL = "http://localhost:3000/api/jobs"

SYSTEM_PROMPT = """You are a structured data extractor for LinkedIn job postings. You receive
raw text captured from specific DOM selectors on a LinkedIn job page. Each
section is delimited by "---" and labeled with [field:] and [selector:].

EXTRACTION RULES BY FIELD:

## company
Two sections may be present with [field: company]:
1. Selector "job-details-about-company-name-link" — contains the company
   name as a clean text string.
2. Selector "job-details-about-company-module" — contains a block starting
   with "About the company", then company name on the next line, followed
   by follower count, industry, company description, and promotional text.
   The company name is the second line of this block.

## title
The section [field: title] contains an aria-label from the apply button.
Two patterns exist:
- "Easy Apply to {TITLE} at {COMPANY}" — title is the text between
  "Easy Apply to " and " at {company}"
- "Apply to {TITLE} on company website" — title is the text between
  "Apply to " and " on company website"

Extract only the job title. Do NOT include "Easy Apply to", "Apply to",
"at {company}", or "on company website" in the extracted title.

## top_card
The section [field: top_card] contains the job's metadata card. It has
this structure (some lines may be absent):

  {company}
  Share
  Show more options
  {title}
  {LOCATION} · {time_posted} · {applicant_count}
  {promotion_line}
  {SALARY}            — optional, e.g. "$130K/yr - $170K/yr"
   {WORK_MODE}        — "Remote", "Hybrid", or "On-site"
  Matches your job preferences, workplace type is {work_mode}.
   {JOB_TYPE}         — "Full-time", "Part-time", "Contract", "Internship"
  Matches your job preferences, job type is {job_type}.
  Easy Apply / Apply
  Save
  Save {title} at {company}

Extract from this section:
- location: text before the first " · " on the location line
- salary_min, salary_max: parse from salary line if present
  - "$130K/yr - $170K/yr" → salary_min=130000, salary_max=170000
  - "$50/hr - $75/hr" → convert to annual (x2080): salary_min=104000, salary_max=156000
  - "$99,000 - $232,000" → salary_min=99000, salary_max=232000
  - salary_currency: "USD" for "$"
  - Salary may also appear in [field: description] as a range embedded in a
    paragraph (e.g. "The salary range for this position is: $X - $Y").
    If salary is absent from top_card, check the description for it.
- work_mode: normalize to one of: "remote", "hybrid", "onsite"
- job_type: normalize to one of: "full_time", "part_time", "contract", "internship"

If a line is not present in the raw text, return null for that field.

## description
The section [field: description] contains the full job description.
Return the complete text as-is. Do not summarize or truncate.

CROSS-VALIDATION:
Several fields appear in multiple sections. Use ALL occurrences to
cross-validate your extraction:

- company: appears in [field: company] (both selectors), [field: title]
  aria-label ("{title} at {company}"), and [field: top_card] (first line
  and "Save {title} at {company}")
- title: appears in [field: title] aria-label, [field: top_card] (line
  after "Show more options"), and [field: top_card] "Save {title} at
  {company}"
- location: appears in [field: top_card] location line
- work_mode: appears in [field: top_card] as a standalone line and in
  "Matches your job preferences, workplace type is {work_mode}"
- job_type: appears in [field: top_card] as a standalone line and in
  "Matches your job preferences, job type is {job_type}"

If values conflict across sections, extract the value that appears most
consistently across all sources. A conflict may indicate an extraction
error in one of the sources.

GENERAL RULES:
- title and company are REQUIRED. Never return empty strings for these.
- description is REQUIRED. Return the full job description text.
- If salary is not shown, return null for salary_min, salary_max,
  salary_currency.
- Normalize work_mode to one of: remote, hybrid, onsite
- Normalize job_type to one of: full_time, part_time, contract, internship
- Do not invent or infer data that is not present in the raw text."""


def extract_fields(state: ExtractionState) -> ExtractionState:
    llm = get_linkedin_model()
    structured_llm = llm.with_structured_output(LinkedInJobExtraction, method="function_calling")

    raw_text = state["raw_text"]
    validation_errors = state.get("validation_errors", [])

    if validation_errors:
        error_feedback = (
            "The previous extraction had the following validation errors. "
            "Please fix them:\n"
            + "\n".join(f"- {e}" for e in validation_errors)
            + "\n\nHere is the raw text to extract from:\n"
            + raw_text
        )
        human_content = error_feedback
        retry_count = state.get("retry_count", 0) + 1
    else:
        human_content = raw_text
        retry_count = state.get("retry_count", 0)

    result = structured_llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=human_content),
    ])

    return {
        **state,
        "extracted": result.model_dump(),
        "retry_count": retry_count,
    }


def validate_fields(state: ExtractionState) -> ExtractionState:
    extracted = state.get("extracted") or {}
    data = LinkedInJobExtraction.model_construct(**extracted)
    errors = validate_extraction(data)
    return {**state, "validation_errors": errors}


def _should_retry(state: ExtractionState) -> str:
    if not state.get("validation_errors"):
        return "insert_job"
    if state.get("retry_count", 0) < 1:
        return "extract_fields"
    return "fail"


def _handle_failure(state: ExtractionState) -> ExtractionState:
    errors = state.get("validation_errors", [])
    error_msg = "Extraction failed validation after retry: " + "; ".join(errors)
    logger.warning(error_msg)
    return {**state, "error": error_msg}


def insert_job(state: ExtractionState) -> ExtractionState:
    extracted = state.get("extracted") or {}
    body = {
        "title": extracted.get("title"),
        "company": extracted.get("company"),
        "url": state.get("url"),
        "description": extracted.get("description"),
        "location": extracted.get("location"),
        "salaryMin": extracted.get("salary_min"),
        "salaryMax": extracted.get("salary_max"),
        "salaryCurrency": extracted.get("salary_currency"),
        "jobType": extracted.get("job_type"),
        "workMode": extracted.get("work_mode"),
        "source": "linkedin",
    }

    try:
        response = httpx.post(NEXTJS_JOBS_URL, json=body)
        response.raise_for_status()
        data = response.json()
        logger.info("Inserted job %s: %s at %s", data.get("id"), body["title"], body["company"])
        return {**state, "job_id": data.get("id")}
    except Exception as exc:
        logger.error("Failed to insert job: %s", exc)
        return {**state, "error": f"Failed to insert job: {exc}"}


def build_extraction_graph() -> StateGraph:
    graph = StateGraph(ExtractionState)

    graph.add_node("extract_fields", extract_fields)
    graph.add_node("validate_fields", validate_fields)
    graph.add_node("insert_job", insert_job)
    graph.add_node("fail", _handle_failure)

    graph.set_entry_point("extract_fields")
    graph.add_edge("extract_fields", "validate_fields")
    graph.add_conditional_edges(
        "validate_fields",
        _should_retry,
        {
            "insert_job": "insert_job",
            "extract_fields": "extract_fields",
            "fail": "fail",
        },
    )
    graph.add_edge("insert_job", END)
    graph.add_edge("fail", END)

    return graph


def run_extraction_pipeline(raw_text: str, url: str) -> dict:
    initial_state: ExtractionState = {
        "raw_text": raw_text,
        "url": url,
        "extracted": None,
        "validation_errors": [],
        "retry_count": 0,
        "job_id": None,
        "error": None,
    }

    try:
        compiled = build_extraction_graph().compile()
        result = compiled.invoke(initial_state)
        return {"job_id": result.get("job_id"), "error": result.get("error")}
    except Exception as exc:
        return {"job_id": None, "error": str(exc)}
