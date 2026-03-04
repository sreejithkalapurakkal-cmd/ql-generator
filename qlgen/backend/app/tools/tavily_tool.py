import httpx
from strands import tool
from app.config import get_settings

settings = get_settings()

TAVILY_API_KEY = settings.TAVILY_API_KEY
TAVILY_BASE_URL = settings.TAVILY_BASE_URL

RATE_LIMIT_CODES = {429, 402, 403}
RATE_LIMIT_MSG = (
    "RATE_LIMITED: Tavily API quota exceeded. Do NOT retry this tool. "
    "Switch immediately to free alternatives: use duckduckgo_search for "
    "news, funding rounds, and company research, and scrape_webpage on "
    "relevant pages."
)


@tool
def tavily_search(query: str, max_results: int = 5, search_depth: str = "advanced") -> dict:
    """
    Web search using Tavily API.
    BEST FOR: Finding recent news, funding rounds, company announcements,
    technology adoption signals, and job postings.
    USE IN STAGES: Company Discovery (Stage 1), BANT Scoring (Stage 4)

    Args:
        query: Search query
        max_results: Maximum number of results
        search_depth: 'basic' or 'advanced' (advanced = more detailed)

    Returns:
        dict with 'results' list containing title, url, content, score
    """
    url = f"{TAVILY_BASE_URL}/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
        "include_raw_content": False,
    }

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
