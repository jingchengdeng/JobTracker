"""LinkedIn profile search via Brave Search API and Playwright/Google fallback."""

import asyncio
import logging
import os
import re
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

SEARCH_DELAY_SECONDS = 1.5

# Chromium args to reduce bot detection footprint.
_BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
]

# JS snippet injected before every navigation to mask webdriver flag.
_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
"""


async def launch_stealth_browser(playwright, headless: bool = True):
    """Launch Chromium with basic anti-detection settings.

    When headless=False, attempts to use Xvfb via PyVirtualDisplay for a
    virtual display. Falls back to headless if Xvfb is unavailable.
    Returns (browser, display) tuple. Caller must stop display after browser.close().
    """
    display = None
    if not headless and not os.environ.get("DISPLAY"):
        try:
            from pyvirtualdisplay import Display
            display = Display(visible=0, size=(1920, 1080))
            display.start()
            logger.info("Started Xvfb virtual display")
        except (ImportError, FileNotFoundError) as exc:
            logger.warning("Xvfb unavailable (%s), falling back to headless", exc)
            headless = True

    browser = await playwright.chromium.launch(
        headless=headless,
        args=_BROWSER_ARGS,
    )
    return browser, display


async def _new_stealth_page(browser):
    """Create a new page with stealth JS pre-injected."""
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        locale="en-US",
    )
    await context.add_init_script(_STEALTH_JS)
    page = await context.new_page()
    return page

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

# Extracts hostname from a URL.
_DOMAIN_RE = re.compile(r"https?://([^/]+)")

# Domains to skip when searching for a company's website.
_DOMAIN_EXCLUDED = {
    "google.com", "linkedin.com", "facebook.com", "twitter.com",
    "youtube.com", "instagram.com", "wikipedia.org", "brave.com",
    "glassdoor.com", "indeed.com", "reddit.com", "bing.com",
}


def _extract_root_domain(hostname: str) -> str:
    """Extract root domain from a full hostname (e.g., 'resources.deloitte.com' -> 'deloitte.com')."""
    parts = hostname.split(".")
    if len(parts) <= 2:
        return hostname
    # Handle common two-part TLDs like co.uk, com.au
    if parts[-2] in ("co", "com", "org", "net", "gov", "ac") and len(parts[-1]) <= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _is_excluded_domain(root: str) -> bool:
    """Return True if the root domain should be skipped."""
    return any(root == excl or root.endswith("." + excl) for excl in _DOMAIN_EXCLUDED)


# --- Brave Search API (primary, no browser needed) ---

_BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


async def brave_search_profiles(query: str, api_key: str, max_results: int = 15) -> list[dict]:
    """Search Brave for LinkedIn profiles. Returns parsed person records."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                _BRAVE_ENDPOINT,
                params={"q": query, "count": max_results},
                headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
                timeout=15.0,
            )
        if resp.status_code != 200:
            logger.warning("Brave API returned %s for '%s'", resp.status_code, query[:80])
            return []
        data = resp.json()
    except Exception as exc:
        logger.warning("Brave API search failed for '%s': %s", query[:80], exc)
        return []

    seen: set[str] = set()
    results: list[dict] = []

    for r in data.get("web", {}).get("results", []):
        href = r.get("url", "")
        m = _LINKEDIN_URL_RE.search(href)
        if not m:
            continue

        slug = m.group(1)
        canonical_url = f"https://www.linkedin.com/in/{slug}"
        if canonical_url in seen:
            continue
        seen.add(canonical_url)

        title_text = r.get("title", "")
        li_idx = title_text.find("LinkedIn")
        if li_idx > 0:
            title_text = title_text[:li_idx]
        title_text = re.sub(r"\s*[|\-\u2013]\s*$", "", title_text).strip()

        name, title = "", ""
        name_m = _NAME_TITLE_RE.match(title_text)
        if name_m:
            name = name_m.group(1).strip()
            title = name_m.group(2).strip()

        description = r.get("description", "")
        location = ""
        loc_m = _LOCATION_RE.search(description)
        if loc_m:
            location = loc_m.group(1).strip()

        results.append({
            "name": name,
            "title": title,
            "location": location,
            "linkedin_url": canonical_url,
        })

    return results


async def brave_search_domain(company: str, api_key: str) -> str | None:
    """Search Brave for a company's website domain.

    Returns root domain (e.g., 'deloitte.com' not 'resources.deloitte.com').
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                _BRAVE_ENDPOINT,
                params={"q": f'"{company}" official website', "count": 5},
                headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
                timeout=15.0,
            )
        if resp.status_code != 200:
            logger.warning("Brave domain search returned %s for '%s'", resp.status_code, company)
            return None
        data = resp.json()
    except Exception as exc:
        logger.warning("Brave domain search failed for '%s': %s", company, exc)
        return None

    for r in data.get("web", {}).get("results", []):
        href = r.get("url", "")
        m = _DOMAIN_RE.search(href)
        if m:
            root = _extract_root_domain(m.group(1).lower())
            if not _is_excluded_domain(root):
                return root
    return None


def build_search_url(query: str) -> str:
    """Build a Google search URL from a query string."""
    return f"https://www.google.com/search?q={quote_plus(query)}&num=10"


def is_captcha_page(page_text: str) -> bool:
    """Check if page content indicates a Google CAPTCHA or block."""
    lower = page_text.lower()
    markers = [
        "unusual traffic",
        "captcha",
        "automated queries",
        "not a robot",
    ]
    for marker in markers:
        if marker in lower:
            logger.warning("CAPTCHA marker matched: '%s'", marker)
            return True
    return False


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
    page = await _new_stealth_page(browser)
    try:
        url = build_search_url(query)
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(1.5)
        text = await page.inner_text("body")

        if is_captcha_page(text):
            logger.warning("Google CAPTCHA detected for query: %s", query[:80])
            return []

        return parse_search_results(text)
    except Exception as exc:
        logger.warning("Google search failed for query '%s': %s", query[:80], exc)
        return []
    finally:
        await page.context.close()
