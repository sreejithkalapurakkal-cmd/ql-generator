from strands import tool


@tool
def duckduckgo_search(query: str, max_results: int = 10) -> list[dict]:
    """
    Free web search using DuckDuckGo.
    BEST FOR: General fallback when other search tools are rate-limited.
    Also useful for finding company websites, LinkedIn profiles, and team pages.
    USE IN STAGES: Any stage as needed.

    Args:
        query: Search query string
        max_results: Number of results to return

    Returns:
        list of dicts with 'title', 'href', 'body' for each result
    """
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return results
    except Exception as e:
        return [{"error": str(e)}]
