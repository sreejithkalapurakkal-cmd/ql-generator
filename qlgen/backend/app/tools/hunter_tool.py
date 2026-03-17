import httpx
from strands import tool
from app.config import get_settings

RATE_LIMIT_CODES = {429, 402, 403}
RATE_LIMIT_MSG = (
    "RATE_LIMITED: Hunter API quota exceeded. Do NOT retry this tool. "
    "Switch immediately to free alternatives: use duckduckgo_search to find "
    "email addresses (search '[name] [company] email' or '[company] contact'), "
    "and scrape_webpage on the company's contact or team page."
)


@tool
def hunter_domain_search(domain: str, limit: int = 10) -> dict:
    """
    Find email addresses associated with a company domain using Hunter.io.
    BEST FOR: Discovering contacts at a company when you know the domain.
    USE IN STAGE: Contact Discovery (Stage 2)

    Args:
        domain: Company domain (e.g., "acme.com")
        limit: Max number of results

    Returns:
        dict with 'data' containing 'emails' list with value, type, confidence, first_name,
        last_name, position, department, linkedin
    """
    settings = get_settings()
    url = f"{settings.HUNTER_BASE_URL}/domain-search"
    params = {"domain": domain, "api_key": settings.HUNTER_API_KEY, "limit": limit}

    try:
        response = httpx.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True, "data": {"emails": []}}
        return {"error": str(e), "data": {"emails": []}}
    except Exception as e:
        return {"error": str(e), "data": {"emails": []}}


@tool
def hunter_email_finder(domain: str, first_name: str, last_name: str) -> dict:
    """
    Find a specific person's email address at a company using Hunter.io.
    BEST FOR: Getting email for a known person when you have their name + company domain.
    USE IN STAGE: Enrichment (Stage 3)

    Args:
        domain: Company domain
        first_name: Person's first name
        last_name: Person's last name

    Returns:
        dict with email, confidence score, and sources
    """
    settings = get_settings()
    url = f"{settings.HUNTER_BASE_URL}/email-finder"
    params = {
        "domain": domain,
        "first_name": first_name,
        "last_name": last_name,
        "api_key": settings.HUNTER_API_KEY,
    }

    try:
        response = httpx.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True, "data": {}}
        return {"error": str(e), "data": {}}
    except Exception as e:
        return {"error": str(e), "data": {}}
