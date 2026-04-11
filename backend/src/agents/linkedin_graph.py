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
    launch_stealth_browser,
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




async def _review_leadership_impl(state: LinkedinState) -> dict:
    """Shared body for the two review_leadership_* nodes.

    Returns a fresh ``{"search_results": {"leadership": [...]}}`` dict when a
    Brave retry found replacement results, or ``{}`` otherwise. Never mutates
    the existing search_results dict in state — parallel nodes may hold
    references to it.
    """
    results = state.get("search_results") or {}
    leadership = results.get("leadership")
    analysis = state.get("analysis")
    if not leadership or not analysis:
        return {}
    review = await run_review_leadership(leadership, analysis["role_domain"])
    if review.needs_retry and review.refined_query and state.get("brave_key"):
        retry_q = f'site:linkedin.com/in "{review.refined_query}" {state["job"]["company"]}'
        try:
            retry_results = await brave_search_profiles(retry_q, state["brave_key"])
        except Exception:
            logger.exception("review_leadership retry failed")
            return {}
        if retry_results:
            return {"search_results": {"leadership": retry_results}}
    return {}


@track_node("linkedin", "review_leadership_brave", TrackBehavior.SINGLE_SHOT)
async def review_leadership_brave_node(state: LinkedinState) -> dict:
    return await _review_leadership_impl(state)


@track_node("linkedin", "review_leadership_playwright", TrackBehavior.SINGLE_SHOT)
async def review_leadership_playwright_node(state: LinkedinState) -> dict:
    return await _review_leadership_impl(state)


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


@track_node("linkedin", "_company_branch_entry", TrackBehavior.SINGLE_SHOT)
async def company_branch_entry_node(state: LinkedinState) -> dict:
    """Pass-through to hold the company-branch conditional edge.

    LangGraph requires a node to attach ``add_conditional_edges`` to; this
    node exists purely so the fork from load_brave_key can route into
    _company_domain_gate without conflicting with the build_queries fork.
    """
    return {}


async def _analyze_jd_gate(state: LinkedinState) -> str:
    """Skip analyze_jd for basic mode (no description, no title)."""
    return "analyze_jd" if state.get("mode") == "full" else "load_brave_key"


async def _fork_after_brave_key(state: LinkedinState) -> list[str]:
    """Unconditionally fan out into both the company and connection branches.

    Returning a list from a conditional router tells LangGraph to schedule
    both targets in the same superstep.
    """
    return ["_company_branch_entry", "build_queries"]


async def _company_domain_gate(state: LinkedinState) -> str:
    """Route the company branch: skip domain search if we already have one,
    otherwise pick the Brave or Playwright lane."""
    if state.get("domain"):
        return "enrich_company_apollo"
    if state.get("brave_key"):
        return "brave_domain_search"
    return "launch_browser"


async def _connection_lane_gate(state: LinkedinState) -> list[str]:
    """Route the connection branch into all 5 parallel search nodes for the
    active lane. The inactive lane's 5 nodes simply never run."""
    if state.get("brave_key"):
        return [
            "brave_recruiter", "brave_ta", "brave_hiring_mgr",
            "brave_hr", "brave_leadership",
        ]
    return ["launch_browser"]


async def _review_brave_gate(state: LinkedinState) -> str:
    results = state.get("search_results") or {}
    if results.get("leadership") and state.get("analysis"):
        return "review_leadership_brave"
    return "merge_dedup"


async def _review_playwright_gate(state: LinkedinState) -> str:
    results = state.get("search_results") or {}
    if results.get("leadership") and state.get("analysis"):
        return "review_leadership_playwright"
    return "close_browser"


def build_linkedin_graph() -> StateGraph:
    graph = StateGraph(LinkedinState)

    # Main spine
    graph.add_node("load_job", load_job_node)
    graph.add_node("precondition_check", precondition_check_node)
    graph.add_node("analyze_jd", analyze_jd_node)
    graph.add_node("load_brave_key", load_brave_key_node)

    # Company branch
    graph.add_node("_company_branch_entry", company_branch_entry_node)
    graph.add_node("brave_domain_search", brave_domain_search_node)
    graph.add_node("browser_domain_search", browser_domain_search_node)
    graph.add_node("enrich_company_apollo", enrich_apollo_node)
    graph.add_node("compile_summary", compile_summary_node)

    # Connection branch
    graph.add_node("build_queries", build_queries_node)
    graph.add_node("launch_browser", launch_browser_node)
    for tag in SEARCH_TAGS:
        graph.add_node(f"brave_{tag}", make_brave_search_node(tag))
        graph.add_node(f"browser_{tag}", make_browser_search_node(tag))
    graph.add_node("review_leadership_brave", review_leadership_brave_node)
    graph.add_node("review_leadership_playwright", review_leadership_playwright_node)
    graph.add_node("close_browser", close_browser_node)

    # Post-branch spine
    graph.add_node("merge_dedup", merge_dedup_node)
    graph.add_node("score_relevance", score_relevance_node)
    graph.add_node("filter_rank", filter_rank_node)
    graph.add_node("generate_notes", generate_notes_node)
    # defer=True so save_results waits for both branches (company +
    # connection) to converge before running. Without this, compile_summary
    # and generate_notes land in different supersteps and save_results fires
    # twice — double-writing contacts and re-flipping the search status.
    graph.add_node("save_results", save_results_node, defer=True)

    # Entry + preamble
    graph.set_entry_point("load_job")
    graph.add_edge("load_job", "precondition_check")
    graph.add_conditional_edges(
        "precondition_check",
        _analyze_jd_gate,
        {"analyze_jd": "analyze_jd", "load_brave_key": "load_brave_key"},
    )
    graph.add_edge("analyze_jd", "load_brave_key")

    # Fork into both branches
    graph.add_conditional_edges(
        "load_brave_key",
        _fork_after_brave_key,
        ["_company_branch_entry", "build_queries"],
    )

    # Company branch routing
    graph.add_conditional_edges(
        "_company_branch_entry",
        _company_domain_gate,
        {
            "enrich_company_apollo": "enrich_company_apollo",
            "brave_domain_search": "brave_domain_search",
            "launch_browser": "launch_browser",
        },
    )
    graph.add_edge("brave_domain_search", "enrich_company_apollo")
    graph.add_edge("browser_domain_search", "enrich_company_apollo")
    graph.add_edge("enrich_company_apollo", "compile_summary")
    graph.add_edge("compile_summary", "save_results")

    # Connection branch routing
    graph.add_conditional_edges(
        "build_queries",
        _connection_lane_gate,
        [
            "brave_recruiter", "brave_ta", "brave_hiring_mgr",
            "brave_hr", "brave_leadership", "launch_browser",
        ],
    )

    # launch_browser fans out to all Playwright consumers
    for tag in SEARCH_TAGS:
        graph.add_edge("launch_browser", f"browser_{tag}")
    graph.add_edge("launch_browser", "browser_domain_search")

    # Brave lane fan-in into merge_dedup
    for tag in ("recruiter", "ta", "hiring_mgr", "hr"):
        graph.add_edge(f"brave_{tag}", "merge_dedup")
    graph.add_conditional_edges(
        "brave_leadership",
        _review_brave_gate,
        {
            "review_leadership_brave": "review_leadership_brave",
            "merge_dedup": "merge_dedup",
        },
    )
    graph.add_edge("review_leadership_brave", "merge_dedup")

    # Playwright lane fan-in through close_browser
    for tag in ("recruiter", "ta", "hiring_mgr", "hr"):
        graph.add_edge(f"browser_{tag}", "close_browser")
    graph.add_conditional_edges(
        "browser_leadership",
        _review_playwright_gate,
        {
            "review_leadership_playwright": "review_leadership_playwright",
            "close_browser": "close_browser",
        },
    )
    graph.add_edge("review_leadership_playwright", "close_browser")
    graph.add_edge("close_browser", "merge_dedup")

    # Post-branch main spine
    graph.add_edge("merge_dedup", "score_relevance")
    graph.add_edge("score_relevance", "filter_rank")
    graph.add_edge("filter_rank", "generate_notes")
    graph.add_edge("generate_notes", "save_results")
    graph.add_edge("save_results", END)

    return graph


linkedin_graph = build_linkedin_graph().compile()
