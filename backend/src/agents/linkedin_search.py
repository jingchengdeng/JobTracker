"""Playwright-based Google search for LinkedIn profiles."""

import asyncio
import logging
import re
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

SEARCH_DELAY_SECONDS = 2.0

# Matches a full linkedin.com/in/<slug> URL, with or without https://www. prefix.
_LINKEDIN_URL_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/in/([\w\-]+)"
)

# "Firstname Lastname - Title" line that commonly appears just above a result.
_NAME_TITLE_RE = re.compile(
    r"([A-Z][a-zA-ZÀ-ÖØ-öø-ÿ'\-]+(?: [A-Z][a-zA-ZÀ-ÖØ-öø-ÿ'\-]+)+)\s*[-–]\s*(.+)"
)

# Location patterns: "City, State, Country" or "City, State"
_LOCATION_RE = re.compile(
    r"([A-Z][a-zA-Z\s]+,\s*[A-Z][a-zA-Z\s]+(?:,\s*[A-Z][a-zA-Z\s]+)?)\s*·"
)


def build_search_url(query: str) -> str:
    """Build a Google search URL from a query string."""
    return f"https://www.google.com/search?q={quote_plus(query)}&num=10"


def is_captcha_page(page_text: str) -> bool:
    """Check if page content indicates a Google CAPTCHA or block."""
    lower = page_text.lower()
    return any(marker in lower for marker in [
        "unusual traffic",
        "captcha",
        "blocked",
        "automated queries",
        "not a robot",
    ])


def _extract_name_near_url(lines: list[str], url_idx: int) -> tuple[str, str]:
    """Search the lines just before a URL line for a 'Name - Title' pattern.

    Returns (name, title) strings, both empty string if nothing found.
    """
    # Look back up to 5 lines for a Name - Title pattern
    for i in range(url_idx - 1, max(url_idx - 6, -1), -1):
        m = _NAME_TITLE_RE.match(lines[i].strip())
        if m:
            return m.group(1).strip(), m.group(2).strip()
    return "", ""


def _extract_location_near_url(lines: list[str], url_idx: int) -> str:
    """Search the lines just after a URL line for a location pattern.

    Returns location string, or empty string if nothing found.
    """
    # Look forward up to 3 lines for a location
    for i in range(url_idx + 1, min(url_idx + 4, len(lines))):
        m = _LOCATION_RE.search(lines[i])
        if m:
            return m.group(1).strip()
    return ""


def parse_search_results(
    page_text: str, prefix: str = "https://www.linkedin.com/in/"
) -> list[dict]:
    """Parse Google search result text and extract LinkedIn profile info.

    Extracts name, title, location, and LinkedIn URL from the text content
    of a Google search results page.

    Returns list of dicts with keys: name, title, location, linkedin_url
    """
    if not page_text:
        return []

    lines = page_text.splitlines()
    seen: set[str] = set()
    results: list[dict] = []

    for idx, line in enumerate(lines):
        m = _LINKEDIN_URL_RE.search(line)
        if not m:
            continue

        slug = m.group(1)
        canonical_url = f"https://www.linkedin.com/in/{slug}"

        if canonical_url in seen:
            continue
        seen.add(canonical_url)

        name, title = _extract_name_near_url(lines, idx)
        location = _extract_location_near_url(lines, idx)

        results.append(
            {
                "name": name,
                "title": title,
                "location": location,
                "linkedin_url": canonical_url,
            }
        )

    return results


async def run_google_search(browser, query: str) -> list[dict]:
    """Run a single Google search using an existing browser instance.

    Opens a new page, navigates to Google, reads results, closes page.
    Returns list of parsed person records, or empty list if CAPTCHA/error.
    """
    page = await browser.new_page()
    try:
        url = build_search_url(query)
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(1.0)
        text = await page.inner_text("body")

        if is_captcha_page(text):
            logger.warning("Google CAPTCHA detected for query: %s", query[:80])
            return []

        return parse_search_results(text)
    except Exception as exc:
        logger.warning("Google search failed for query '%s': %s", query[:80], exc)
        return []
    finally:
        await page.close()
