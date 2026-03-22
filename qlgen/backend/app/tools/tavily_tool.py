import httpx
from strands import tool
from app.config import get_settings

RATE_LIMIT_CODES = {429, 402, 403, 401}
RATE_LIMIT_MSG = (
    "RATE_LIMITED: Tavily API quota exceeded. Do NOT retry this tool. "
    "Switch immediately to free alternatives: use duckduckgo_search for "
    "news, funding rounds, and company research, and scrape_webpage on "
    "relevant pages."
)


@tool
def tavily_search(
    query: str,
    max_results: int = 15,
    search_depth: str = "advanced",
    include_domains: list[str] = None,
    topic: str = None,
) -> dict:
    """
    Web search using Tavily API.
    BEST FOR: Finding recent news, funding rounds, company announcements,
    technology adoption signals, and job postings.
    USE IN STAGES: Company Discovery (Stage 1), BANT Scoring (Stage 4)

    Args:
        query: Search query
        max_results: Maximum number of results (default 15, max 20)
        search_depth: 'basic' or 'advanced' (advanced = more detailed)
        include_domains: List of domains to restrict search to
            (e.g., ["crunchbase.com", "g2.com", "techcrunch.com"])
        topic: Search topic filter — "general" (default) or "news" (for recent news only)

    Returns:
        dict with 'results' list containing title, url, content, score
    """
    settings = get_settings()
    url = f"{settings.TAVILY_BASE_URL}/search"
    payload = {
        "api_key": settings.TAVILY_API_KEY,
        "query": query,
        "max_results": min(max_results, 20),
        "search_depth": search_depth,
        "include_raw_content": False,
        "include_domains": include_domains,
        "topic": topic,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        response = httpx.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True, "results": []}
        return {"error": str(e), "results": []}
    except Exception as e:
        return {"error": str(e), "results": []}
