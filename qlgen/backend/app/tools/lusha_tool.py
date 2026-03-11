import uuid

import httpx
from strands import tool
from app.config import get_settings

RATE_LIMIT_CODES = {429, 402, 403}
RATE_LIMIT_MSG = (
    "RATE_LIMITED: Lusha API quota exceeded. Do NOT retry this tool. "
    "Switch immediately to free alternatives: use duckduckgo_search to find "
    "phone numbers (search '[name] [company] phone' or '[name] [company] contact'), "
    "and scrape_webpage on the company's contact page or team directory."
)


@tool
def lusha_person_search(
    first_name: str,
    last_name: str,
    company_name: str = None,
    company_domain: str = None,
    linkedin_url: str = None,
    email: str = None,
) -> dict:
    """
    Look up phone numbers and email for a specific person using Lusha API v2.
    BEST FOR: Getting phone numbers when you already have a LinkedIn URL or email.
    USE IN STAGE: Enrichment (Stage 3)

    Priority lookup order:
    1. linkedin_url — most reliable if available from Stage 2
    2. email — also highly reliable
    3. first_name + last_name + company_name/domain (less reliable)

    Args:
        first_name: Person's first name
        last_name: Person's last name
        company_name: Company name for disambiguation
        company_domain: Company website domain
        linkedin_url: LinkedIn profile URL (preferred — highest match rate)
        email: Known email address for enrichment

    Returns:
        dict with phone numbers, email addresses, and company data
    """
    settings = get_settings()
    url = f"{settings.LUSHA_BASE_URL}/v2/person"
    headers = {"api_key": settings.LUSHA_API_KEY, "Content-Type": "application/json"}

    contact_id = str(uuid.uuid4())[:8]
    contact: dict = {"contactId": contact_id}

    # Lusha v2 accepts: linkedinUrl, email, or personId per contact
    if linkedin_url:
        contact["linkedinUrl"] = linkedin_url.strip()
    elif email:
        contact["email"] = email.strip()
    else:
        # Lusha v2 does not accept firstName/lastName/domain directly.
        # Return a clear message so the agent can try a different tool.
        return {
            "error": (
                "Lusha requires a LinkedIn URL or email to look up a contact. "
                "Use find_linkedin_profiles or hunter_domain_search first to get "
                "a LinkedIn URL or email, then call lusha_person_search with it."
            ),
            "phones": [],
            "emails": [],
        }

    payload = {"contacts": [contact]}

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Lusha v2 response: {"contacts": {contactId: {data: {...}, error: ...}}, "companies": {...}}
        contacts_result = data.get("contacts", {})
        contact_data = contacts_result.get(contact_id, {})

        if contact_data.get("error"):
            err = contact_data["error"]
            return {
                "error": f"Lusha returned no data: {err.get('name', 'EMPTY_DATA')} (code {err.get('code', '?')}). "
                         "This person may not be in Lusha's database.",
                "phones": [],
                "emails": [],
            }

        person = contact_data.get("data") or {}
        phones = []
        for ph in person.get("phones", []):
            phones.append({
                "number": ph.get("number") or ph.get("internationalNumber", ""),
                "type": ph.get("type", ""),
            })

        emails = []
        for em in person.get("emails", []):
            emails.append({
                "email": em.get("email", ""),
                "type": em.get("type", ""),
            })

        companies = data.get("companies", {})
        company_info = next(iter(companies.values()), {}) if companies else {}

        return {
            "full_name": person.get("fullName", f"{first_name} {last_name}").strip(),
            "phones": phones,
            "emails": emails,
            "company": company_info.get("name", company_name or ""),
            "title": person.get("jobTitle", ""),
            "linkedin_url": person.get("linkedinUrl", linkedin_url or ""),
        }

    except httpx.HTTPStatusError as e:
        if e.response.status_code in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True, "phones": [], "emails": []}
        return {"error": str(e), "phones": [], "emails": []}
    except Exception as e:
        return {"error": str(e), "phones": [], "emails": []}
