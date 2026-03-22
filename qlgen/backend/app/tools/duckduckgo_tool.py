from strands import tool

from app.tools.ddg_rate_limiter import ddg_search as _ddg_search_via_limiter


@tool
def duckduckgo_search(query: str, max_results: int = 10) -> list[dict]:
    """
    Free web search using DuckDuckGo.
    BEST FOR: General fallback when other search tools are rate-limited.
    Also useful for finding company websites, LinkedIn profiles, and team pages.
    USE IN STAGES: Any stage as needed.

    NOTE: DuckDuckGo rate-limits aggressive automated queries. Keep max_results
    at 10 or below, and avoid calling this tool more than 5 times in quick
    succession. If you get a rate_limited response, STOP using this tool and
    switch to other search tools (exa_search, tavily_search).

    Args:
        query: Search query string
        max_results: Number of results to return (keep at 10 or below to avoid rate limits)

    Returns:
        list of dicts with 'title', 'href', 'body' for each result
    """
    return _ddg_search_via_limiter(query, max_results=max_results)
