import logging
import httpx
from strands import tool
from app.config import get_settings

logger = logging.getLogger(__name__)

RATE_LIMIT_CODES = {429, 402}
RATE_LIMIT_MSG = (
    "RATE_LIMITED: Apollo API quota exceeded. Do NOT retry this tool. "
    "Switch immediately to free alternatives: use exa_search, tavily_search, "
    "or duckduckgo_search for company discovery."
)


@tool
def apollo_company_search(
    query: str,
    industries: list[str] = None,
    locations: list[str] = None,
    min_employees: int = None,
    max_employees: int = None,
    page: int = 1,
    per_page: int = 25,
) -> dict:
    """
    Search for companies using Apollo.io API.
    BEST FOR: Structured company database search with filters for industry,
    location, employee count, and revenue range.
    USE IN STAGE: Company Discovery (Stage 1)

    IMPORTANT: The 'industries' parameter accepts freeform industry keywords
    (e.g., "medical devices", "healthcare technology"). These are merged into
    the keyword search — Apollo does not require internal tag IDs.

    Args:
        query: Search query describing the type of company (e.g., "medical device manufacturer")
        industries: Optional list of industry terms to add as keyword tags
            (e.g., ["medical devices", "healthcare technology"])
        locations: List of locations (cities, states, countries)
        min_employees: Minimum number of employees
        max_employees: Maximum number of employees
        page: Page number for pagination
        per_page: Results per page (max 25)

    Returns:
        dict with 'organizations' list and 'pagination' info
    """
    settings = get_settings()
    url = f"{settings.APOLLO_BASE_URL}/mixed_companies/search"
    headers = {
        "X-Api-Key": settings.APOLLO_API_KEY,
        "Content-Type": "application/json",
    }

    # Merge query + industries into keyword_tags (Apollo's freeform keyword field).
    # Do NOT use organization_industry_tag_ids — that requires Apollo's internal
    # numeric tag IDs and rejects freeform text with a 422 error.
    keyword_tags = []
    if query:
        keyword_tags.append(query)
    if industries:
        keyword_tags.extend(industries)

    payload = {
        "q_organization_keyword_tags": keyword_tags if keyword_tags else None,
        "organization_locations": locations,
        "organization_num_employees_ranges": (
            [f"{min_employees or ''},{max_employees or ''}"]
            if min_employees or max_employees
            else None
        ),
        "page": page,
        "per_page": per_page,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    logger.info(f"Apollo company search payload: {payload}")

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        resp_body = ""
        try:
            resp_body = e.response.text[:500]
        except Exception:
            pass
        logger.warning(f"Apollo HTTP {e.response.status_code}: {resp_body}")

        if e.response.status_code in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True, "organizations": []}
        if e.response.status_code == 422:
            return {
                "error": (
                    f"Apollo rejected the request (422 Unprocessable Entity). "
                    f"Simplify the query — try fewer keywords or remove filters. "
                    f"Details: {resp_body}"
                ),
                "organizations": [],
            }
        if e.response.status_code in (401, 403):
            return {
                "error": f"Apollo authentication error ({e.response.status_code}). Check API key.",
                "organizations": [],
            }
        return {"error": str(e), "organizations": []}
    except Exception as e:
        return {"error": str(e), "organizations": []}


@tool
def apollo_people_search(
    company_name: str = None,
    company_domain: str = None,
    titles: list[str] = None,
    locations: list[str] = None,
    page: int = 1,
    per_page: int = 10,
) -> dict:
    """
    Search for people/contacts at specific companies using Apollo.io.
    BEST FOR: Finding decision-makers by title at known companies.
    USE IN STAGE: Contact Discovery (Stage 2)

    Args:
        company_name: Name of the company to search within
        company_domain: Domain of the company (e.g., "acme.com")
        titles: List of job titles to filter by (e.g., ["CTO", "VP Engineering"])
        locations: List of locations to filter
        page: Page number
        per_page: Results per page

    Returns:
        dict with 'people' list containing name, title, email, linkedin, phone
    """
    settings = get_settings()
    url = f"{settings.APOLLO_BASE_URL}/mixed_people/search"
    headers = {
        "X-Api-Key": settings.APOLLO_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "q_organization_name": company_name,
        "organization_domains": [company_domain] if company_domain else None,
        "person_titles": titles,
        "person_locations": locations,
        "page": page,
        "per_page": per_page,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True, "people": []}
        if e.response.status_code == 422:
            body = ""
            try:
                body = e.response.text[:300]
            except Exception:
                pass
            return {
                "error": (
                    f"Apollo rejected the request (422). Try simpler parameters. "
                    f"Details: {body}"
                ),
                "people": [],
            }
        return {"error": str(e), "people": []}
    except Exception as e:
        return {"error": str(e), "people": []}
