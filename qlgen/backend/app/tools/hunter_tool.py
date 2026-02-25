import httpx
from strands import tool
from app.config import get_settings

settings = get_settings()

HUNTER_API_KEY = settings.HUNTER_API_KEY
HUNTER_BASE_URL = settings.HUNTER_BASE_URL


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
    url = f"{HUNTER_BASE_URL}/domain-search"
    params = {"domain": domain, "api_key": HUNTER_API_KEY, "limit": limit}

    try:
        response = httpx.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
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
    url = f"{HUNTER_BASE_URL}/email-finder"
    params = {
        "domain": domain,
        "first_name": first_name,
        "last_name": last_name,
        "api_key": HUNTER_API_KEY,
    }

    try:
        response = httpx.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e), "data": {}}
