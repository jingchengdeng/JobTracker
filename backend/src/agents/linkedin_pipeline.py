"""LinkedIn search pipeline — deterministic LangGraph-style pipeline."""

import asyncio
import json
import logging

import httpx
from langchain_core.messages import SystemMessage, HumanMessage

from src.agents.linkedin_db import (
    create_search, update_search_status, save_company_data, save_contacts, load_search,
)
from src.agents.linkedin_schemas import (
    JdAnalysis, RelevanceScores, ConnectionNotes, CompanySummary, LeadershipReview,
)
from src.agents.linkedin_search import brave_search_profiles, brave_search_domain, SEARCH_DELAY_SECONDS
from src.models.provider import get_linkedin_model
from src.auth.credentials import load_api_key

logger = logging.getLogger(__name__)

RELEVANCE_THRESHOLD = 40
MAX_CONTACTS = 10
LOW_CONFIDENCE_COUNT = 3
NOTE_MAX_CHARS = 300
NOTE_TARGET_CHARS = 280


# --- Pure / deterministic functions ---

def precondition_check(job: dict) -> dict:
    """Determine pipeline mode based on available job data."""
    has_description = bool(job.get("description") and job["description"].strip())
    has_title = bool(job.get("title") and job["title"].strip())
    if has_description or has_title:
        return {"mode": "full", "job": job}
    return {"mode": "basic", "job": job}


def build_search_queries(company: str, analysis: dict | None) -> list[dict]:
    """Build search queries using site: operator (works on both Brave and Google)."""
    base_queries = [
        {"query": f'site:linkedin.com/in "recruiter" "{company}"', "tag": "recruiter"},
        {"query": f'site:linkedin.com/in "talent acquisition" "{company}"', "tag": "ta"},
        {"query": f'site:linkedin.com/in "hiring manager" "{company}"', "tag": "hiring_mgr"},
        {"query": f'site:linkedin.com/in "HR manager" "{company}"', "tag": "hr"},
    ]
    if analysis:
        leadership_title = analysis["leadership_titles"][0] if analysis["leadership_titles"] else "Engineering Manager"
        base_queries.append({
            "query": f'site:linkedin.com/in "{leadership_title}" "{company}"',
            "tag": "leadership",
        })
    return base_queries


def merge_and_deduplicate(search_results: dict[str, list[dict]]) -> list[dict]:
    """Merge results from multiple searches, dedup by LinkedIn URL."""
    seen: dict[str, dict] = {}
    for tag, people in search_results.items():
        for person in people:
            url = person["linkedin_url"]
            if url in seen:
                existing_tags = seen[url]["source_query"]
                if tag not in existing_tags:
                    seen[url]["source_query"] = f"{existing_tags},{tag}"
            else:
                seen[url] = {**person, "source_query": tag}
    return list(seen.values())


def filter_and_rank(people: list[dict]) -> list[dict]:
    """Filter by relevance threshold, cap at max, handle low-confidence fallback."""
    sorted_people = sorted(people, key=lambda p: p["relevance_score"], reverse=True)
    above_threshold = [p for p in sorted_people if p["relevance_score"] >= RELEVANCE_THRESHOLD]

    if above_threshold:
        result = above_threshold[:MAX_CONTACTS]
        for p in result:
            p["low_confidence"] = 0
        return result
    else:
        result = sorted_people[:LOW_CONFIDENCE_COUNT]
        for p in result:
            p["low_confidence"] = 1
        return result


def truncate_note(note: str) -> str:
    """Truncate a connection note to 300 chars at a word boundary."""
    if len(note) <= NOTE_MAX_CHARS:
        return note.strip()
    truncated = note[:NOTE_MAX_CHARS]
    last_space = truncated.rfind(" ")
    if last_space > 200:
        truncated = truncated[:last_space]
    return truncated.strip()


# --- LLM nodes ---

def run_analyze_jd(job: dict) -> dict:
    """Analyze the JD to extract role info. Returns dict matching JdAnalysis fields."""
    llm = get_linkedin_model()
    structured = llm.with_structured_output(JdAnalysis, method="function_calling")
    description = job.get("description") or ""
    title = job.get("title") or ""
    prompt = (
        f"Analyze this job posting and extract structured information.\n\n"
        f"Job title: {title}\n\n"
        f"Job description:\n{description[:3000]}\n\n"
        "Extract the role title, department domain, seniority level, "
        "leadership titles one level above this role, and relevant department keywords."
    )
    result = structured.invoke([HumanMessage(content=prompt)])
    return result.model_dump()


def run_extract_domain(job: dict) -> str | None:
    """Try to extract a company domain from the JD text."""
    description = job.get("description") or ""
    if not description.strip():
        return None
    llm = get_linkedin_model()
    prompt = (
        "Extract the company's website domain from this job description. "
        "Look for URLs, email addresses, or explicit mentions of the company website. "
        "Return ONLY the domain (e.g., 'stripe.com') or the word 'none' if no domain is found. "
        "Do not guess — only return a domain if you find explicit evidence.\n\n"
        f"Job description:\n{description[:3000]}"
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    raw = response.content
    if isinstance(raw, list):
        raw = "".join(block.get("text", "") if isinstance(block, dict) else str(block) for block in raw)
    text = raw.strip().lower()
    if text == "none" or len(text) > 100 or " " in text:
        return None
    # Clean up common prefixes
    for prefix in ["http://", "https://", "www."]:
        if text.startswith(prefix):
            text = text[len(prefix):]
    return text.rstrip("/") if "." in text else None


def run_score_relevance(people: list[dict], job: dict, analysis: dict | None) -> list[dict]:
    """Score each person for relevance to the job."""
    if not people:
        return []
    llm = get_linkedin_model()
    structured = llm.with_structured_output(RelevanceScores, method="function_calling")
    people_text = "\n".join(
        f"- {p['name']} | {p['title']} | {p['location'] or 'Unknown'} | {p['linkedin_url']}"
        for p in people
    )
    context = ""
    if analysis:
        context = (
            f"Role: {analysis['role_title']}, Domain: {analysis['role_domain']}, "
            f"Seniority: {analysis['seniority']}"
        )
    else:
        context = f"Company: {job['company']}, Title: {job.get('title', 'Unknown')}"

    prompt = (
        f"Score each person's relevance (0-100) to this job context: {context}\n\n"
        "Higher scores for: recruiters/TA specialists at the company, hiring managers "
        "for the relevant department, HR business partners. Lower scores for: people in "
        "unrelated departments, very junior roles, people who may have left the company.\n\n"
        f"People to score:\n{people_text}"
    )
    result = structured.invoke([HumanMessage(content=prompt)])
    score_map = {s.linkedin_url: s.score for s in result.scores}
    for person in people:
        person["relevance_score"] = score_map.get(person["linkedin_url"], 50)
    return people


def run_generate_notes(people: list[dict], job: dict) -> list[dict]:
    """Generate personalized connection notes for each person."""
    if not people:
        return []
    llm = get_linkedin_model()
    structured = llm.with_structured_output(ConnectionNotes, method="function_calling")
    people_text = "\n".join(
        f"- {p['name']} ({p['title']}) | {p['linkedin_url']}" for p in people
    )
    prompt = (
        f"Generate a personalized LinkedIn connection note for each person below. "
        f"The user is applying for the '{job.get('title', 'a role')}' position at {job['company']}.\n\n"
        f"Each note must be under {NOTE_TARGET_CHARS} characters. Be concise, professional, "
        f"and specific to the person's role. Mention the job title and company.\n\n"
        f"People:\n{people_text}"
    )
    result = structured.invoke([HumanMessage(content=prompt)])
    note_map = {n.linkedin_url: n.note for n in result.notes}
    for person in people:
        raw_note = note_map.get(person["linkedin_url"], f"Hi {person['name']}, I'm interested in the {job.get('title', '')} role at {job['company']}.")
        person["connection_note"] = truncate_note(raw_note)
    return people


def run_compile_summary(company_data: dict, job: dict) -> str:
    """Generate an interview-prep company summary from Apollo data."""
    llm = get_linkedin_model()
    structured = llm.with_structured_output(CompanySummary, method="function_calling")
    # Pick the most relevant fields
    fields = {
        "name": company_data.get("name"),
        "short_description": company_data.get("short_description"),
        "industry": company_data.get("industry"),
        "estimated_num_employees": company_data.get("estimated_num_employees"),
        "founded_year": company_data.get("founded_year"),
        "annual_revenue_printed": company_data.get("annual_revenue_printed"),
        "total_funding_printed": company_data.get("total_funding_printed"),
        "latest_funding_stage": company_data.get("latest_funding_stage"),
        "departmental_head_count": company_data.get("departmental_head_count"),
        "keywords": (company_data.get("keywords") or [])[:20],
        "technology_names": (company_data.get("technology_names") or [])[:20],
    }
    prompt = (
        f"Write a 2-3 paragraph company summary oriented toward interview preparation "
        f"for someone applying to the '{job.get('title', 'a role')}' position.\n\n"
        f"Company data:\n{json.dumps(fields, indent=2)}\n\n"
        "Focus on: what the company does, scale and financial health, relevant tech stack, "
        "department size if available, and any insights useful for interview prep."
    )
    result = structured.invoke([HumanMessage(content=prompt)])
    return result.summary


def run_review_leadership(people: list[dict], role_domain: str) -> LeadershipReview:
    """Review leadership search results for relevance to the role domain."""
    if not people:
        return LeadershipReview(relevant_count=0, total_count=0, needs_retry=False, refined_query=None)
    llm = get_linkedin_model()
    structured = llm.with_structured_output(LeadershipReview, method="function_calling")
    people_text = "\n".join(f"- {p['name']} | {p['title']}" for p in people)
    prompt = (
        f"Review these search results. The target role domain is '{role_domain}'. "
        f"Count how many people are relevant to this domain (e.g., for 'engineering', "
        f"an 'Engineering Director' is relevant but an 'HR Director' is not).\n\n"
        f"People:\n{people_text}\n\n"
        f"If more than 50% are irrelevant, set needs_retry=true and suggest a refined "
        f"search query that adds '{role_domain}' to narrow results."
    )
    return structured.invoke([HumanMessage(content=prompt)])


# --- Apollo integration ---

async def enrich_company_apollo(domain: str) -> dict | None:
    """Call Apollo Organization Enrichment API."""
    api_key = load_api_key("apollo")
    if not api_key:
        logger.warning("No Apollo API key configured, skipping enrichment")
        return None
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "https://api.apollo.io/api/v1/organizations/enrich",
            params={"domain": domain},
            headers={"x-api-key": api_key},
        )
        if resp.status_code != 200:
            logger.warning("Apollo enrichment failed for %s: %s", domain, resp.status_code)
            return None
        data = resp.json()
        return data.get("organization")


# --- Browser domain search ---

async def search_domain_google(browser, company: str) -> str | None:
    """Search Google for a company's domain using Playwright."""
    from src.agents.linkedin_search import build_search_url, _new_stealth_page
    import re

    page = await _new_stealth_page(browser)
    try:
        url = build_search_url(f'"{company}" official website')
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(1.5)
        text = await page.inner_text("body")

        # Look for domain patterns in results
        domain_pattern = re.compile(r'https?://(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,})')
        matches = domain_pattern.findall(text)
        # Filter out google, linkedin, etc.
        excluded = {"google.com", "linkedin.com", "facebook.com", "twitter.com", "youtube.com", "instagram.com", "wikipedia.org"}
        for domain in matches:
            if domain.lower() not in excluded:
                return domain.lower()
        return None
    except Exception as exc:
        logger.warning("Domain search failed for '%s': %s", company, exc)
        return None
    finally:
        await page.context.close()


# --- Main pipeline entry point ---

async def run_linkedin_pipeline(search_id: int, job_id: int) -> None:
    """Run the full linkedin search pipeline. Called as a background asyncio task.

    Uses Brave Search API when key is configured (no browser needed).
    Falls back to headed Google via Xvfb if no Brave key, or headless as last resort.
    """
    from src.db import get_connection

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, title, company, description FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
    finally:
        conn.close()

    if not row:
        update_search_status(search_id, "failed")
        return

    job = dict(row)
    loop = asyncio.get_running_loop()

    try:
        # 1. Precondition check
        check = precondition_check(job)
        mode = check["mode"]

        # 2. Analyze JD (if full mode)
        analysis = None
        if mode == "full":
            analysis = await loop.run_in_executor(None, run_analyze_jd, job)

        # 3. Extract domain from JD text
        domain = None
        if job.get("description"):
            domain = await loop.run_in_executor(None, run_extract_domain, job)
        logger.warning("Domain from JD extraction: %s", domain)

        # 4. Check for Brave API key
        brave_key = load_api_key("brave")

        # 5. Domain search fallback (if JD extraction found nothing)
        if not domain and brave_key:
            domain = await loop.run_in_executor(None, brave_search_domain, job["company"], brave_key)
            logger.warning("Domain from Brave search: %s", domain)

        # 6. Apollo enrichment (if domain found + key configured)
        company_data = None
        if domain:
            company_data = await enrich_company_apollo(domain)
            logger.warning("Apollo enrichment result: %s", "success" if company_data else "no data")

        # 7. Build and run search queries
        queries = build_search_queries(job["company"], analysis)
        search_results: dict[str, list[dict]] = {}

        if brave_key:
            # Brave API path (no browser needed)
            for q in queries:
                results = await loop.run_in_executor(
                    None, brave_search_profiles, q["query"], brave_key, 15
                )
                search_results[q["tag"]] = results
                logger.warning("Brave search '%s': %d results", q["tag"], len(results))
                await asyncio.sleep(SEARCH_DELAY_SECONDS)
        else:
            # Browser fallback path (Google via Playwright)
            from playwright.async_api import async_playwright
            from src.agents.linkedin_search import launch_stealth_browser, run_google_search

            async with async_playwright() as pw:
                browser, display = await launch_stealth_browser(pw, headless=False)
                try:
                    # Domain search via browser if still needed
                    if not domain:
                        domain = await search_domain_google(browser, job["company"])
                        logger.warning("Domain from Google search: %s", domain)
                        await asyncio.sleep(SEARCH_DELAY_SECONDS)

                        # Apollo enrichment with browser-found domain
                        if domain and not company_data:
                            company_data = await enrich_company_apollo(domain)

                    # Profile searches via browser
                    for q in queries:
                        results = await run_google_search(browser, q["query"])
                        search_results[q["tag"]] = results
                        logger.warning("Google search '%s': %d results", q["tag"], len(results))
                        await asyncio.sleep(SEARCH_DELAY_SECONDS)
                finally:
                    await browser.close()
                    if display:
                        display.stop()

        # 8. Review leadership results (if applicable)
        if "leadership" in search_results and analysis and search_results["leadership"]:
            review = await loop.run_in_executor(
                None, run_review_leadership, search_results["leadership"], analysis["role_domain"]
            )
            if review.needs_retry and review.refined_query:
                retry_query = f'site:linkedin.com/in "{review.refined_query}" "{job["company"]}"'
                if brave_key:
                    retry_results = await loop.run_in_executor(
                        None, brave_search_profiles, retry_query, brave_key
                    )
                else:
                    logger.warning("Leadership retry skipped — no Brave key, browser already closed")
                    retry_results = []
                search_results["leadership"] = retry_results
                await asyncio.sleep(SEARCH_DELAY_SECONDS)

        # 9. Merge and deduplicate
        merged = merge_and_deduplicate(search_results)
        logger.warning("Merged contacts: %d", len(merged))

        # 10. Score relevance
        if merged:
            merged = await loop.run_in_executor(None, run_score_relevance, merged, job, analysis)

        # 11. Filter and rank
        ranked = filter_and_rank(merged)

        # 12. Generate connection notes
        if ranked:
            ranked = await loop.run_in_executor(None, run_generate_notes, ranked, job)

        # 13. Compile company summary
        summary = None
        if company_data:
            summary = await loop.run_in_executor(None, run_compile_summary, company_data, job)

        # 14. Save results
        if company_data or domain:
            save_company_data(
                search_id,
                domain=domain or "",
                data_json=json.dumps(company_data) if company_data else "{}",
                summary=summary or "",
            )

        save_contacts(search_id, ranked)
        update_search_status(search_id, "completed")

    except Exception as exc:
        logger.exception("LinkedIn pipeline failed for search %s: %s", search_id, exc)
        update_search_status(search_id, "failed")
