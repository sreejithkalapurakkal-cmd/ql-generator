import logging
import httpx
from strands import tool
from app.config import get_settings

logger = logging.getLogger(__name__)

RATE_LIMIT_CODES = {429, 402, 403}
RATE_LIMIT_MSG = (
    "RATE_LIMITED: Clay API quota exceeded. Do NOT retry this tool. "
    "Use alternative enrichment tools instead."
)


@tool
def clay_enrich_company(
    domain: str,
) -> dict:
    """
    Enrich a company using Clay's data enrichment platform (50+ data providers).
    BEST FOR: Getting comprehensive firmographic data — employee count, revenue,
    industry, tech stack, funding, and more — in a single API call.
    USE IN STAGES: Firmographic Fit (Stage 2), Signal Research (Stage 3)

    Args:
        domain: Company domain (e.g., "acme.com")

    Returns:
        dict with enriched company data including employee_count, revenue,
        industry, tech_stack, funding_total, last_funding_date, etc.
    """
    settings = get_settings()
    if not settings.CLAY_API_KEY:
        return {"error": "Clay API key not configured. Use alternative enrichment tools.", "data": {}}

    url = f"{settings.CLAY_BASE_URL}/v1/enrichment/company"
    headers = {
        "Authorization": f"Bearer {settings.CLAY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"domain": domain}

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Normalize response to consistent format
        result = {
            "domain": domain,
            "name": data.get("name"),
            "industry": data.get("industry"),
            "sub_industry": data.get("sub_industry"),
            "employee_count": data.get("employee_count"),
            "revenue_estimate": data.get("revenue") or data.get("annual_revenue"),
            "founding_year": data.get("founding_year") or data.get("founded_year"),
            "tech_stack": data.get("tech_stack", []),
            "funding_total": data.get("funding_total"),
            "last_funding_date": data.get("last_funding_date"),
            "last_funding_amount": data.get("last_funding_amount"),
            "funding_stage": data.get("funding_stage"),
            "description": data.get("description"),
            "city": data.get("city"),
            "state": data.get("state"),
            "country": data.get("country"),
            "linkedin_url": data.get("linkedin_url"),
            "raw_data": data,
        }
        return {k: v for k, v in result.items() if v is not None}

    except httpx.HTTPStatusError as e:
        resp_body = ""
        try:
            resp_body = e.response.text[:500]
        except Exception:
            pass
        logger.warning(f"Clay company HTTP {e.response.status_code}: {resp_body}")

        if e.response.status_code == 404:
            return {
                "error": "DEPRECATED: Clay enrichment API endpoint no longer exists (404). "
                "Do NOT call this tool again. Use apollo_company_search or exa_search instead.",
                "deprecated": True, "data": {},
            }
        if e.response.status_code in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True, "data": {}}
        return {"error": f"Clay API error ({e.response.status_code}): {resp_body}", "data": {}}
    except Exception as e:
        return {"error": str(e), "data": {}}


@tool
def clay_enrich_person(
    linkedin_url: str = None,
    email: str = None,
    first_name: str = None,
    last_name: str = None,
    company_domain: str = None,
) -> dict:
    """
    Enrich a person/contact using Clay's enrichment platform.
    BEST FOR: Getting verified contact details — email, phone, title,
    LinkedIn profile, and employment history.
    USE IN STAGE: Contact Discovery (Stage 4)

    Provide at least one of: linkedin_url, email, or (first_name + last_name + company_domain).
    LinkedIn URL provides the highest match rate.

    Args:
        linkedin_url: Person's LinkedIn profile URL (best identifier)
        email: Person's email address
        first_name: Person's first name
        last_name: Person's last name
        company_domain: Current company domain for disambiguation

    Returns:
        dict with enriched person data including verified email, phone,
        current title, linkedin_url, etc.
    """
    settings = get_settings()
    if not settings.CLAY_API_KEY:
        return {"error": "Clay API key not configured. Use alternative tools.", "data": {}}

    url = f"{settings.CLAY_BASE_URL}/v1/enrichment/person"
    headers = {
        "Authorization": f"Bearer {settings.CLAY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {}
    if linkedin_url:
        payload["linkedin_url"] = linkedin_url
    if email:
        payload["email"] = email
    if first_name:
        payload["first_name"] = first_name
    if last_name:
        payload["last_name"] = last_name
    if company_domain:
        payload["company_domain"] = company_domain

    if not payload:
        return {"error": "Provide at least linkedin_url, email, or name + company_domain", "data": {}}

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        result = {
            "full_name": data.get("full_name"),
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "email": data.get("email"),
            "email_verified": data.get("email_verified", False),
            "phone": data.get("phone"),
            "title": data.get("title") or data.get("job_title"),
            "linkedin_url": data.get("linkedin_url"),
            "company": data.get("company"),
            "company_domain": data.get("company_domain"),
            "city": data.get("city"),
            "country": data.get("country"),
            "raw_data": data,
        }
        return {k: v for k, v in result.items() if v is not None}

    except httpx.HTTPStatusError as e:
        resp_body = ""
        try:
            resp_body = e.response.text[:500]
        except Exception:
            pass
        logger.warning(f"Clay person HTTP {e.response.status_code}: {resp_body}")

        if e.response.status_code == 404:
            return {
                "error": "DEPRECATED: Clay enrichment API endpoint no longer exists (404). "
                "Do NOT call this tool again. Use apollo_people_search or find_company_executives instead.",
                "deprecated": True, "data": {},
            }
        if e.response.status_code in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True, "data": {}}
        return {"error": f"Clay API error ({e.response.status_code}): {resp_body}", "data": {}}
    except Exception as e:
        return {"error": str(e), "data": {}}
