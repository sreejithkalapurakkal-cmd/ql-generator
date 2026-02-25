import httpx
from strands import tool
from app.config import get_settings

settings = get_settings()

APOLLO_API_KEY = settings.APOLLO_API_KEY
APOLLO_BASE_URL = settings.APOLLO_BASE_URL


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

    Args:
        query: Search query describing the type of company (e.g., "ecommerce fashion")
        industries: List of industry verticals to filter by
        locations: List of locations (cities, states, countries)
        min_employees: Minimum number of employees
        max_employees: Maximum number of employees
        page: Page number for pagination
        per_page: Results per page (max 25)

    Returns:
        dict with 'organizations' list and 'pagination' info
    """
    url = f"{APOLLO_BASE_URL}/mixed_companies/search"
    payload = {
        "api_key": APOLLO_API_KEY,
        "q_organization_keyword_tags": [query] if query else None,
        "organization_industry_tag_ids": industries,
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

    try:
        response = httpx.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
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
    url = f"{APOLLO_BASE_URL}/mixed_people/search"
    payload = {
        "api_key": APOLLO_API_KEY,
        "q_organization_name": company_name,
        "organization_domains": [company_domain] if company_domain else None,
        "person_titles": titles,
        "person_locations": locations,
        "page": page,
        "per_page": per_page,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        response = httpx.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e), "people": []}
