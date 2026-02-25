import httpx
from strands import tool
from app.config import get_settings

settings = get_settings()

TAVILY_API_KEY = settings.TAVILY_API_KEY
TAVILY_BASE_URL = settings.TAVILY_BASE_URL


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
    except Exception as e:
        return {"error": str(e), "results": []}
