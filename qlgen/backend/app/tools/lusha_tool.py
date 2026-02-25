import httpx
from strands import tool
from app.config import get_settings

settings = get_settings()

LUSHA_API_KEY = settings.LUSHA_API_KEY
LUSHA_BASE_URL = settings.LUSHA_BASE_URL


@tool
def lusha_person_search(
    first_name: str,
    last_name: str,
    company_name: str = None,
    company_domain: str = None,
) -> dict:
    """
    Look up phone numbers and email for a specific person using Lusha.
    BEST FOR: Getting phone numbers when you already have name + company.
    USE IN STAGE: Enrichment (Stage 3)

    Args:
        first_name: Person's first name
        last_name: Person's last name
        company_name: Company name for disambiguation
        company_domain: Company website domain

    Returns:
        dict with phone numbers, email addresses, and social profiles
    """
    url = f"{LUSHA_BASE_URL}/person"
    headers = {"api_key": LUSHA_API_KEY, "Content-Type": "application/json"}
    payload = {
        "firstName": first_name,
        "lastName": last_name,
        "company": company_name,
        "domain": company_domain,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}
