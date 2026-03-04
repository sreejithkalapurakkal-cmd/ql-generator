import httpx
from strands import tool
from app.config import get_settings

settings = get_settings()

EXA_API_KEY = settings.EXA_API_KEY
EXA_BASE_URL = settings.EXA_BASE_URL

RATE_LIMIT_CODES = {429, 402, 403}
RATE_LIMIT_MSG = (
    "RATE_LIMITED: Exa API quota exceeded. Do NOT retry this tool. "
    "Switch immediately to free alternatives: use duckduckgo_search with "
    "targeted queries and scrape_webpage on relevant pages."
)


@tool
def exa_search(
    query: str,
    num_results: int = 10,
    use_autoprompt: bool = True,
    include_domains: list[str] = None,
    exclude_domains: list[str] = None,
    category: str = None,
) -> dict:
    """
    Neural/semantic web search using Exa API.
    BEST FOR: Finding companies by qualitative descriptions - tech stack,
    business model, growth signals. Also good for finding LinkedIn profiles.
    USE IN STAGES: Company Discovery (Stage 1), Enrichment (Stage 3)

    Args:
        query: Natural language search query (e.g., "midsize ecommerce companies using Shopify Plus in California")
        num_results: Number of results to return (max 50)
        use_autoprompt: Let Exa optimize the query
        include_domains: Only search these domains
        exclude_domains: Exclude these domains
        category: Filter category (company, research_paper, news, etc.)

    Returns:
        dict with 'results' list containing url, title, text, author, published_date
    """
    url = f"{EXA_BASE_URL}/search"
    headers = {
        "x-api-key": EXA_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "numResults": num_results,
        "useAutoprompt": use_autoprompt,
        "includeDomains": include_domains,
        "excludeDomains": exclude_domains,
        "category": category,
        "contents": {"text": {"maxCharacters": 2000}},
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True, "results": []}
        return {"error": str(e), "results": []}
    except Exception as e:
        return {"error": str(e), "results": []}
