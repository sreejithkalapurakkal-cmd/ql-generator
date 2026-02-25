import httpx
import structlog
from strands import tool

from config import settings

logger = structlog.get_logger()


@tool
def exa_search(query: str, max_results: int = 10) -> list[dict]:
    """
    Perform a semantic search for companies using Exa.

    Args:
        query: Natural language query for finding companies
        max_results: Maximum number of results to return (default: 10)

    Returns:
        List of search results with title, url, and content
    """
    if not settings.exa_api_key:
        logger.warning("exa_search skipped: no API key configured")
        return []

    try:
        response = httpx.post(
            "https://api.exa.ai/search",
            headers={
                "x-api-key": settings.exa_api_key,
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "numResults": max_results,
                "type": "neural",
                "useAutoprompt": True,
                "contents": {
                    "text": {"maxCharacters": 1000},
                },
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
                "content": item.get("text", ""),
                "domain": _extract_domain(item.get("url", "")),
                "published_date": item.get("publishedDate"),
            })

        logger.info("exa_search completed", query=query, result_count=len(results))
        return results

    except Exception as e:
        logger.error("exa_search failed", query=query, error=str(e))
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
