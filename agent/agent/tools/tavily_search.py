import httpx
import structlog
from strands import tool

from config import settings

logger = structlog.get_logger()


@tool
def tavily_search(query: str, max_results: int = 10) -> list[dict]:
    """
    Search the web for companies matching a query using Tavily.

    Args:
        query: Search query optimized for finding B2B companies
        max_results: Maximum number of results to return (default: 10)

    Returns:
        List of search results with title, url, and content snippet
    """
    if not settings.tavily_api_key:
        logger.warning("tavily_search skipped: no API key configured")
        return []

    try:
        response = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.tavily_api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "advanced",
                "include_domains": [],
                "exclude_domains": [],
            },
            timeout=settings.tool_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "domain": _extract_domain(item.get("url", "")),
            })

        logger.info("tavily_search completed", query=query, result_count=len(results))
        return results

    except Exception as e:
        logger.error("tavily_search failed", query=query, error=str(e))
        raise


def _extract_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""
