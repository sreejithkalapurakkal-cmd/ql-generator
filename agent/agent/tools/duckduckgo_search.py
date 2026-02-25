import httpx
import structlog
from strands import tool

logger = structlog.get_logger()


@tool
def duckduckgo_search(query: str, max_results: int = 10) -> list[dict]:
    """
    Search the web using DuckDuckGo as a fallback (no API key needed).

    Args:
        query: Search query for finding companies
        max_results: Maximum number of results to return (default: 10)

    Returns:
        List of search results with title, url, and content snippet
    """
    try:
        response = httpx.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_redirect": "1",
                "no_html": "1",
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        results = []

        # Abstract result
        if data.get("Abstract"):
            results.append({
                "title": data.get("Heading", ""),
                "url": data.get("AbstractURL", ""),
                "content": data.get("Abstract", ""),
                "domain": _extract_domain(data.get("AbstractURL", "")),
            })

        # Related topics
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if "Text" in topic:
                results.append({
                    "title": topic.get("Text", "")[:100],
                    "url": topic.get("FirstURL", ""),
                    "content": topic.get("Text", ""),
                    "domain": _extract_domain(topic.get("FirstURL", "")),
                })

        logger.info("duckduckgo_search completed", query=query, result_count=len(results))
        return results[:max_results]

    except Exception as e:
        logger.error("duckduckgo_search failed", query=query, error=str(e))
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
