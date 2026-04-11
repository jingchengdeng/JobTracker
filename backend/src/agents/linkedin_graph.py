"""LinkedIn search pipeline as a LangGraph.

The old imperative `run_linkedin_pipeline` in linkedin_pipeline.py is a 150-line
function with 14 numbered steps. This module wraps each step as a graph node
so the `@track_node` decorator can observe them uniformly. No behavioural
change to the underlying logic.
"""
import asyncio
import json
import logging
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import StateGraph, END
from playwright.async_api import async_playwright

from src.agents.linkedin_db import (
    save_company_data, save_contacts, update_search_status,
)
from src.agents.linkedin_pipeline import (
    precondition_check,
    build_search_queries,
    merge_and_deduplicate,
    filter_and_rank,
    truncate_note,
    run_analyze_jd,
    run_score_relevance,
    run_generate_notes,
    run_compile_summary,
    run_review_leadership,
    enrich_company_apollo,
    search_domain_google,
)
from src.agents.linkedin_search import (
    brave_search_profiles, brave_search_domain, run_google_search,
    launch_stealth_browser, SEARCH_DELAY_SECONDS,
)
from src.agents.pipeline_tracking import track_node, TrackBehavior
from src.auth.credentials import load_api_key
from src.db import get_connection

logger = logging.getLogger(__name__)

# Rate-limit Brave API fan-out. Brave allows ~1 req/sec per key; with 6 possible
# concurrent Brave calls per run (5 profile searches + domain search), bound the
# in-flight count to 3.
_brave_semaphore = asyncio.Semaphore(3)

# Rate-limit Playwright/Google fan-out. Google aggressively CAPTCHAs parallel
# requests from the same IP; keep at most 2 pages in flight.
_playwright_semaphore = asyncio.Semaphore(2)

SEARCH_TAGS = ("recruiter", "ta", "hiring_mgr", "hr", "leadership")


def _query_for_tag(queries: list[dict] | None, tag: str) -> str | None:
    """Return the query string for a given tag, or None if not present.

    build_search_queries only emits the leadership query when analysis exists,
    so 'leadership' may be absent in basic mode.
    """
    for q in queries or []:
        if q.get("tag") == tag:
            return q.get("query")
    return None


def _merge_results(a: dict | None, b: dict | None) -> dict:
    """Reducer for parallel writes to ``search_results``.

    Each search node returns a single-key dict like ``{"recruiter": [...]}``.
    LangGraph calls this reducer with the accumulated dict and each new update,
    merging them key-wise with later-wins semantics on collision (used by the
    two review_leadership nodes to overwrite the leadership slot).
    """
    return {**(a or {}), **(b or {})}


class LinkedinState(TypedDict, total=False):
    search_id: int
    job_id: int
    workflow_run_id: str
    job: dict
    mode: Literal["full", "basic"]
    analysis: dict | None
    domain: str | None
    company_data: dict | None
    brave_key: str | None
    queries: list[dict]
    search_results: Annotated[dict[str, list[dict]], _merge_results]
    browser: Any
    _display: Any
    _playwright: Any
    merged: list[dict]
    ranked: list[dict]
    summary: str | None
    error: str | None


@track_node("linkedin", "load_job", TrackBehavior.SINGLE_SHOT)
async def load_job_node(state: LinkedinState) -> dict:
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT id, title, company, description FROM jobs WHERE id = ?",
            (state["job_id"],),
        )
        row = await cursor.fetchone()
    if not row:
        return {"error": f"Job {state['job_id']} not found"}
    return {"job": dict(row)}


@track_node("linkedin", "precondition_check", TrackBehavior.SINGLE_SHOT)
async def precondition_check_node(state: LinkedinState) -> dict:
    result = await precondition_check(state["job"])
    return result  # already {"mode": ..., "job": ...}


@track_node("linkedin", "analyze_jd", TrackBehavior.SINGLE_SHOT)
async def analyze_jd_node(state: LinkedinState) -> dict:
    analysis = await run_analyze_jd(state["job"])
    domain = analysis.pop("domain", None)
    return {"analysis": analysis, "domain": domain}


@track_node("linkedin", "extract_domain_from_jd", TrackBehavior.SINGLE_SHOT)
async def extract_domain_node(state: LinkedinState) -> dict:
    # Transitional no-op. analyze_jd_node now writes state["domain"] directly;
    # Task 6 deletes this node entirely.
    return {}


@track_node("linkedin", "load_brave_key", TrackBehavior.SINGLE_SHOT)
async def load_brave_key_node(state: LinkedinState) -> dict:
    key = await load_api_key("brave")
    return {"brave_key": key}


@track_node("linkedin", "brave_domain_search", TrackBehavior.SINGLE_SHOT)
async def brave_domain_search_node(state: LinkedinState) -> dict:
    if state.get("domain") or not state.get("brave_key"):
        return {}
    domain = await brave_search_domain(state["job"]["company"], state["brave_key"])
    return {"domain": domain}


@track_node("linkedin", "enrich_company_apollo", TrackBehavior.SINGLE_SHOT)
async def enrich_apollo_node(state: LinkedinState) -> dict:
    if not state.get("domain"):
        return {}
    company_data = await enrich_company_apollo(state["domain"])
    return {"company_data": company_data}


@track_node("linkedin", "build_queries", TrackBehavior.SINGLE_SHOT)
async def build_queries_node(state: LinkedinState) -> dict:
    queries = await build_search_queries(state["job"]["company"], state.get("analysis"))
    return {"queries": queries}


@track_node("linkedin", "run_brave_searches", TrackBehavior.SINGLE_SHOT)
async def run_brave_searches_node(state: LinkedinState) -> dict:
    results: dict[str, list[dict]] = {}
    for q in state["queries"]:
        people = await brave_search_profiles(q["query"], state["brave_key"], 15)
        results[q["tag"]] = people
        await asyncio.sleep(SEARCH_DELAY_SECONDS)
    return {"search_results": results}


@track_node("linkedin", "run_browser_searches", TrackBehavior.SINGLE_SHOT)
async def run_browser_searches_node(state: LinkedinState) -> dict:
    """Playwright path. Opens browser once, closes in finally."""
    from src.agents.linkedin_search import launch_stealth_browser, run_google_search

    results: dict[str, list[dict]] = {}
    domain = state.get("domain")
    company_data = state.get("company_data")

    async with async_playwright() as pw:
        browser, display = await launch_stealth_browser(pw, headless=False)
        try:
            if not domain:
                domain = await search_domain_google(browser, state["job"]["company"])
                await asyncio.sleep(SEARCH_DELAY_SECONDS)
                if domain and not company_data:
                    company_data = await enrich_company_apollo(domain)

            for q in state["queries"]:
                people = await run_google_search(browser, q["query"])
                results[q["tag"]] = people
                await asyncio.sleep(SEARCH_DELAY_SECONDS)
        finally:
            await browser.close()
            if display:
                display.stop()

    return {"search_results": results, "domain": domain, "company_data": company_data}


@track_node("linkedin", "review_leadership", TrackBehavior.SINGLE_SHOT)
async def review_leadership_node(state: LinkedinState) -> dict:
    results = state.get("search_results", {})
    analysis = state.get("analysis")
    if "leadership" not in results or not analysis or not results["leadership"]:
        return {}
    review = await run_review_leadership(results["leadership"], analysis["role_domain"])
    if review.needs_retry and review.refined_query and state.get("brave_key"):
        retry_q = f'site:linkedin.com/in "{review.refined_query}" {state["job"]["company"]}'
        retry_results = await brave_search_profiles(retry_q, state["brave_key"])
        if retry_results:
            results["leadership"] = retry_results
        await asyncio.sleep(SEARCH_DELAY_SECONDS)
    return {"search_results": results}


@track_node("linkedin", "merge_dedup", TrackBehavior.SINGLE_SHOT)
async def merge_dedup_node(state: LinkedinState) -> dict:
    merged = await merge_and_deduplicate(state.get("search_results", {}))
    return {"merged": merged}


@track_node("linkedin", "score_relevance", TrackBehavior.SINGLE_SHOT)
async def score_relevance_node(state: LinkedinState) -> dict:
    merged = state.get("merged", [])
    if not merged:
        return {}
    scored = await run_score_relevance(merged, state["job"], state.get("analysis"))
    return {"merged": scored}


@track_node("linkedin", "filter_rank", TrackBehavior.SINGLE_SHOT)
async def filter_rank_node(state: LinkedinState) -> dict:
    ranked = await filter_and_rank(state.get("merged", []))
    return {"ranked": ranked}


@track_node("linkedin", "generate_notes", TrackBehavior.SINGLE_SHOT)
async def generate_notes_node(state: LinkedinState) -> dict:
    ranked = state.get("ranked", [])
    if not ranked:
        return {}
    with_notes = await run_generate_notes(ranked, state["job"])
    return {"ranked": with_notes}


@track_node("linkedin", "compile_summary", TrackBehavior.SINGLE_SHOT)
async def compile_summary_node(state: LinkedinState) -> dict:
    company_data = state.get("company_data")
    if not company_data:
        return {"summary": None}
    summary = await run_compile_summary(company_data, state["job"])
    return {"summary": summary}


@track_node("linkedin", "save_results", TrackBehavior.SINGLE_SHOT)
async def save_results_node(state: LinkedinState) -> dict:
    if state.get("company_data") or state.get("domain"):
        await save_company_data(
            state["search_id"],
            domain=state.get("domain") or "",
            data_json=json.dumps(state["company_data"]) if state.get("company_data") else "{}",
            summary=state.get("summary") or "",
        )
    await save_contacts(state["search_id"], state.get("ranked", []))
    await update_search_status(state["search_id"], "completed")
    return {}


def make_brave_search_node(tag: str):
    """Factory producing a Brave-backed search node for one query tag.

    Each generated node is registered under a distinct name (``brave_<tag>``)
    so the topology tab renders one box per tag and pipeline_events holds one
    row per tag.
    """

    @track_node("linkedin", f"brave_{tag}", TrackBehavior.SINGLE_SHOT)
    async def node(state: LinkedinState) -> dict:
        query = _query_for_tag(state.get("queries"), tag)
        brave_key = state.get("brave_key")
        if not query or not brave_key:
            return {}
        async with _brave_semaphore:
            try:
                people = await brave_search_profiles(query, brave_key, 15)
            except Exception:
                logger.exception("brave_%s failed", tag)
                people = []
        return {"search_results": {tag: people}}

    node.__name__ = f"brave_{tag}_node"
    return node


def make_browser_search_node(tag: str):
    """Factory producing a Playwright-backed search node for one query tag."""

    @track_node("linkedin", f"browser_{tag}", TrackBehavior.SINGLE_SHOT)
    async def node(state: LinkedinState) -> dict:
        query = _query_for_tag(state.get("queries"), tag)
        browser = state.get("browser")
        if not query or browser is None:
            return {}
        async with _playwright_semaphore:
            try:
                people = await run_google_search(browser, query)
            except Exception:
                logger.exception("browser_%s failed", tag)
                people = []
        return {"search_results": {tag: people}}

    node.__name__ = f"browser_{tag}_node"
    return node


@track_node("linkedin", "launch_browser", TrackBehavior.SINGLE_SHOT)
async def launch_browser_node(state: LinkedinState) -> dict:
    """Start Playwright and launch Chromium exactly once per pipeline run.

    Both entry points into the Playwright lane (company-branch domain search
    and connection-branch 5-way fan-out) route through this node. The
    idempotent guard is defence-in-depth in case the two branches land in
    different supersteps.
    """
    if state.get("browser") is not None:
        return {}
    pw = await async_playwright().start()
    browser, display = await launch_stealth_browser(pw, headless=False)
    return {"browser": browser, "_display": display, "_playwright": pw}


@track_node("linkedin", "close_browser", TrackBehavior.SINGLE_SHOT)
async def close_browser_node(state: LinkedinState) -> dict:
    """Tear down Chromium, the virtual display, and the Playwright driver.

    Tolerant of missing handles so the pipeline keeps running even if launch
    never succeeded.
    """
    browser = state.get("browser")
    if browser is not None:
        try:
            await browser.close()
        except Exception:
            logger.exception("close_browser: browser.close() failed")
    display = state.get("_display")
    if display is not None:
        try:
            display.stop()
        except Exception:
            logger.exception("close_browser: display.stop() failed")
    pw = state.get("_playwright")
    if pw is not None:
        try:
            await pw.stop()
        except Exception:
            logger.exception("close_browser: playwright.stop() failed")
    return {"browser": None, "_display": None, "_playwright": None}


@track_node("linkedin", "browser_domain_search", TrackBehavior.SINGLE_SHOT)
async def browser_domain_search_node(state: LinkedinState) -> dict:
    """Look up a company domain via the shared Playwright browser."""
    if state.get("domain"):
        return {}
    browser = state.get("browser")
    if browser is None:
        return {}
    async with _playwright_semaphore:
        try:
            domain = await search_domain_google(browser, state["job"]["company"])
        except Exception:
            logger.exception("browser_domain_search failed")
            domain = None
    return {"domain": domain} if domain else {}


async def _analyze_jd_gate(state: LinkedinState) -> str:
    return "analyze_jd" if state.get("mode") == "full" else "extract_domain_from_jd"


async def _brave_domain_search_gate(state: LinkedinState) -> str:
    if not state.get("domain") and state.get("brave_key"):
        return "brave_domain_search"
    return "enrich_apollo_gate"


async def _enrich_apollo_gate(state: LinkedinState) -> str:
    return "enrich_company_apollo" if state.get("domain") else "build_queries"


async def _search_path_gate(state: LinkedinState) -> str:
    return "run_brave_searches" if state.get("brave_key") else "run_browser_searches"


async def _review_leadership_gate(state: LinkedinState) -> str:
    results = state.get("search_results", {})
    if results.get("leadership") and state.get("analysis"):
        return "review_leadership"
    return "merge_dedup"


def build_linkedin_graph() -> StateGraph:
    graph = StateGraph(LinkedinState)

    graph.add_node("load_job", load_job_node)
    graph.add_node("precondition_check", precondition_check_node)
    graph.add_node("analyze_jd", analyze_jd_node)
    graph.add_node("extract_domain_from_jd", extract_domain_node)
    graph.add_node("load_brave_key", load_brave_key_node)
    graph.add_node("brave_domain_search", brave_domain_search_node)
    graph.add_node("enrich_company_apollo", enrich_apollo_node)
    graph.add_node("build_queries", build_queries_node)
    graph.add_node("run_brave_searches", run_brave_searches_node)
    graph.add_node("run_browser_searches", run_browser_searches_node)
    graph.add_node("review_leadership", review_leadership_node)
    graph.add_node("merge_dedup", merge_dedup_node)
    graph.add_node("score_relevance", score_relevance_node)
    graph.add_node("filter_rank", filter_rank_node)
    graph.add_node("generate_notes", generate_notes_node)
    graph.add_node("compile_summary", compile_summary_node)
    graph.add_node("save_results", save_results_node)

    graph.set_entry_point("load_job")
    graph.add_edge("load_job", "precondition_check")
    graph.add_conditional_edges(
        "precondition_check",
        _analyze_jd_gate,
        {
            "analyze_jd": "analyze_jd",
            "extract_domain_from_jd": "extract_domain_from_jd",
        },
    )
    graph.add_edge("analyze_jd", "extract_domain_from_jd")
    graph.add_edge("extract_domain_from_jd", "load_brave_key")
    graph.add_conditional_edges(
        "load_brave_key",
        _brave_domain_search_gate,
        {
            "brave_domain_search": "brave_domain_search",
            "enrich_apollo_gate": "enrich_company_apollo",  # fall through
        },
    )
    graph.add_edge("brave_domain_search", "enrich_company_apollo")
    graph.add_conditional_edges(
        "enrich_company_apollo",
        _enrich_apollo_gate,
        {
            "enrich_company_apollo": "build_queries",
            "build_queries": "build_queries",
        },
    )
    graph.add_conditional_edges(
        "build_queries",
        _search_path_gate,
        {
            "run_brave_searches": "run_brave_searches",
            "run_browser_searches": "run_browser_searches",
        },
    )
    graph.add_conditional_edges(
        "run_brave_searches",
        _review_leadership_gate,
        {
            "review_leadership": "review_leadership",
            "merge_dedup": "merge_dedup",
        },
    )
    graph.add_conditional_edges(
        "run_browser_searches",
        _review_leadership_gate,
        {
            "review_leadership": "review_leadership",
            "merge_dedup": "merge_dedup",
        },
    )
    graph.add_edge("review_leadership", "merge_dedup")
    graph.add_edge("merge_dedup", "score_relevance")
    graph.add_edge("score_relevance", "filter_rank")
    graph.add_edge("filter_rank", "generate_notes")
    graph.add_edge("generate_notes", "compile_summary")
    graph.add_edge("compile_summary", "save_results")
    graph.add_edge("save_results", END)

    return graph


linkedin_graph = build_linkedin_graph().compile()
