"""Google Custom Search Engine tool (100 free queries/day).

Uses Google Programmable Search Engine as a fallback to DuckDuckGo for
high-value search queries. Requires GOOGLE_CSE_API_KEY and GOOGLE_CSE_ID
environment variables. 100 free queries/day, 10 results each.
"""

import logging
import os

from strands import tool

from app.tools.retry_utils import httpx_get_with_retry

logger = logging.getLogger(__name__)

GOOGLE_CSE_API = "https://www.googleapis.com/customsearch/v1"


@tool
def google_custom_search(
    query: str,
    num_results: int = 10,
    site_restrict: str = "",
) -> dict:
    """
    Search the web using Google Custom Search Engine.
    Requires GOOGLE_CSE_API_KEY and GOOGLE_CSE_ID env vars.
    Limited to 100 free queries/day — use sparingly for highest-value queries.

    Use as a FALLBACK when DuckDuckGo is rate-limited or for high-precision
    queries like directory lookups, specific company searches, and
    site-restricted searches.

    USE IN STAGES: Stage 1 (Discovery) as DDG fallback, Stage 3 (Signals)
    for specific company news/events.

    Args:
        query: Search query string
        num_results: Number of results (1-10, default 10)
        site_restrict: Optional site restriction (e.g. "linkedin.com")

    Returns:
        dict with 'results' list containing title, link, snippet
    """
    api_key = os.environ.get("GOOGLE_CSE_API_KEY")
    cse_id = os.environ.get("GOOGLE_CSE_ID")

    if not api_key or not cse_id:
        return {
            "error": "GOOGLE_CSE_API_KEY and GOOGLE_CSE_ID env vars required. "
                     "Get free at https://programmablesearchengine.google.com/",
            "results": [],
            "configured": False,
        }

    search_query = query
    if site_restrict:
        search_query = f"site:{site_restrict} {query}"

    try:
        response = httpx_get_with_retry(
            GOOGLE_CSE_API,
            params={
                "key": api_key,
                "cx": cse_id,
                "q": search_query,
                "num": min(num_results, 10),
            },
            timeout=15,
        )

        if response.status_code == 429:
            return {
                "error": "Google CSE daily quota exceeded (100 queries/day)",
                "results": [],
                "quota_exceeded": True,
            }

        if response.status_code != 200:
            return {
                "error": f"Google CSE API returned HTTP {response.status_code}",
                "results": [],
            }

        data = response.json()
        results = []

        for item in data.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "display_link": item.get("displayLink", ""),
            })

        search_info = data.get("searchInformation", {})
        logger.info(
            f"Google CSE: {len(results)} results for '{query}' "
            f"(total ~{search_info.get('totalResults', '?')})"
        )

        return {
            "results": results,
            "total_results": search_info.get("totalResults", "0"),
            "search_time": search_info.get("searchTime", 0),
            "returned": len(results),
        }

    except Exception as e:
        logger.error(f"Google CSE search failed: {e}")
        return {"error": str(e), "results": []}
