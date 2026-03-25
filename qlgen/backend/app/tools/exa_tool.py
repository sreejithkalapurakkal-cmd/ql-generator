import logging
import httpx
from strands import tool
from app.config import get_settings

logger = logging.getLogger(__name__)

RATE_LIMIT_CODES = {429, 402}
RATE_LIMIT_MSG = (
    "RATE_LIMITED: Exa API quota exceeded. Do NOT retry this tool. "
    "Switch to alternatives: use apollo_company_search, tavily_search, "
    "or duckduckgo_search for discovery."
)


def _exa_error_handler(e: httpx.HTTPStatusError, tool_name: str) -> dict:
    """Shared error handler for Exa API responses."""
    resp_body = ""
    try:
        resp_body = e.response.text[:500]
    except Exception:
        pass
    logger.warning(f"Exa {tool_name} HTTP {e.response.status_code}: {resp_body}")

    if e.response.status_code in RATE_LIMIT_CODES:
        return {"error": RATE_LIMIT_MSG, "rate_limited": True, "results": []}
    if e.response.status_code == 400:
        return {
            "error": (
                f"Exa {tool_name} rejected the request (400 Bad Request). "
                f"Simplify the query or check parameter values. "
                f"Details: {resp_body}"
            ),
            "results": [],
        }
    if e.response.status_code in (401, 403):
        return {
            "error": f"Exa authentication error ({e.response.status_code}). Check API key.",
            "results": [],
        }
    return {"error": str(e), "results": []}


def _trim_exa_result(r: dict, include_score: bool = False) -> dict:
    """Trim an Exa result to essential fields."""
    trimmed = {
        "url": r.get("url"),
        "title": r.get("title"),
        "highlights": r.get("highlights", []),
        "text": (r.get("text") or "")[:500],
    }
    if include_score and r.get("score") is not None:
        trimmed["score"] = r.get("score")
    return trimmed


@tool
def exa_search(
    query: str,
    num_results: int = 10,
    use_autoprompt: bool = True,
    include_domains: list[str] = None,
    exclude_domains: list[str] = None,
    category: str = None,
    search_type: str = "auto",
    start_published_date: str = None,
    end_published_date: str = None,
    include_text: list[str] = None,
    exclude_text: list[str] = None,
) -> dict:
    """
    Neural/semantic web search using Exa API.
    BEST FOR: Finding companies by qualitative descriptions - tech stack,
    business model, growth signals. Also good for finding people profiles.
    USE IN STAGES: Company Discovery (Stage 1), Signal Research (Stage 3),
    Contact Discovery (Stage 4)

    Args:
        query: Natural language search query (e.g., "midsize ecommerce companies using Shopify Plus in California")
        num_results: Number of results to return (max 50, default 10).
            Use num_results=30 for Stage 1 discovery queries that need volume.
        use_autoprompt: Let Exa optimize the query
        include_domains: Only search these domains
        exclude_domains: Exclude these domains
        category: Filter category. Options:
            "company" — Focus on company websites (Stage 1 discovery)
            "people" — Search 1B+ indexed profiles (Stage 4 contacts)
            "news" — Focus on news articles (Stage 3 signals)
            "research_paper", "personal_site", "financial_report"
        search_type: Search algorithm type. Options:
            "auto" — Exa chooses best type (default, good general choice)
            "neural" — Semantic/concept search, best for discovery queries
            "keyword" — Traditional keyword matching, good for specific terms
            "instant" — Sub-200ms latency, good for co-pilot interactive queries
        start_published_date: Only return results published after this date.
            ISO format: "2025-09-01T00:00:00.000Z". IMPORTANT for Stage 3 signal
            research — use this to find only RECENT evidence (last 6 months).
        end_published_date: Only return results published before this date.
            ISO format: "2026-03-25T00:00:00.000Z"
        include_text: Only return results containing ALL of these strings.
            Max 1 string, 5 words. Useful for precision filtering:
            e.g., ["funding round"], ["Series B"], ["hiring CTO"]
        exclude_text: Exclude results containing ANY of these strings.
            Max 1 string, 5 words. e.g., ["job listing"] to filter during discovery.

    Returns:
        dict with 'results' list containing url, title, highlights, text
    """
    settings = get_settings()
    url = f"{settings.EXA_BASE_URL}/search"
    headers = {
        "x-api-key": settings.EXA_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "numResults": min(num_results, 50),
        "useAutoprompt": use_autoprompt,
        "type": search_type,
        "includeDomains": include_domains,
        "excludeDomains": exclude_domains,
        "category": category,
        "startPublishedDate": start_published_date,
        "endPublishedDate": end_published_date,
        "includeText": include_text,
        "excludeText": exclude_text,
        "contents": {
            "highlights": {"numSentences": 3, "highlightsPerUrl": 2},
            "text": {"maxCharacters": 600},
        },
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    logger.info(f"Exa search payload: {payload}")

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        if "results" in data:
            data["results"] = [_trim_exa_result(r) for r in data["results"]]
        return data
    except httpx.HTTPStatusError as e:
        return _exa_error_handler(e, "search")
    except Exception as e:
        return {"error": str(e), "results": []}


@tool
def exa_find_similar(
    url: str,
    num_results: int = 15,
    exclude_domains: list[str] = None,
    category: str = None,
) -> dict:
    """
    Find companies/pages similar to a given URL using Exa's neural similarity search.
    BEST FOR: Discovering more companies like a known good match. After finding
    high-scoring ICP matches, use their website URLs to find similar companies.
    USE IN STAGE: Company Discovery (Stage 1)

    Args:
        url: A URL to find similar pages/companies for (e.g., "https://acme.com")
        num_results: Number of similar results to return (max 50, default 15).
            Use num_results=30 for high-value expansion queries.
        exclude_domains: Domains to exclude from results (e.g., exclude already-found companies)
        category: Filter category — use "company" to focus on company websites

    Returns:
        dict with 'results' list containing url, title, highlights, text, score
    """
    settings = get_settings()
    api_url = f"{settings.EXA_BASE_URL}/findSimilar"
    headers = {
        "x-api-key": settings.EXA_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "url": url,
        "numResults": min(num_results, 50),
        "excludeDomains": exclude_domains,
        "category": category,
        "contents": {
            "highlights": {"numSentences": 3, "highlightsPerUrl": 2},
            "text": {"maxCharacters": 600},
        },
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    logger.info(f"Exa findSimilar payload: {payload}")

    try:
        response = httpx.post(api_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        if "results" in data:
            data["results"] = [_trim_exa_result(r, include_score=True) for r in data["results"]]
        return data
    except httpx.HTTPStatusError as e:
        return _exa_error_handler(e, "findSimilar")
    except Exception as e:
        return {"error": str(e), "results": []}


# ──────────────────────────────────────────────────────────────────
# Contents Endpoint (Bulk URL extraction)
# ──────────────────────────────────────────────────────────────────

@tool
def exa_get_contents(
    urls: list[str],
) -> dict:
    """
    Extract clean content from specific URLs using Exa's content extraction.
    BEST FOR: Bulk content extraction from URLs found by other tools (Apollo, Tavily,
    press releases). Accepts up to 10 URLs per call. Cheaper and cleaner than scrape_webpage.
    USE IN STAGES: Signal Research (Stage 3), Co-pilot research

    Args:
        urls: List of URLs to extract content from (max 10).
            Example: ["https://techcrunch.com/article1", "https://company.com/about"]

    Returns:
        dict with 'results' list containing url, title, highlights, text per URL
    """
    settings = get_settings()
    if not urls:
        return {"error": "Provide at least one URL.", "results": []}

    urls = urls[:10]  # Exa batch limit
    api_url = f"{settings.EXA_BASE_URL}/contents"
    headers = {
        "x-api-key": settings.EXA_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "urls": urls,
        "highlights": {"numSentences": 3, "highlightsPerUrl": 2},
        "text": {"maxCharacters": 600},
    }
    logger.info(f"Exa get_contents: {len(urls)} URLs")

    try:
        response = httpx.post(api_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        results = data.get("results") or []
        return {
            "results": [_trim_exa_result(r) for r in results],
            "urls_requested": len(urls),
            "urls_returned": len(results),
        }
    except httpx.HTTPStatusError as e:
        return _exa_error_handler(e, "get_contents")
    except Exception as e:
        return {"error": str(e), "results": []}
