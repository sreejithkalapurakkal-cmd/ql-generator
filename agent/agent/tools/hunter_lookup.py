import httpx
import structlog
from strands import tool

from config import settings

logger = structlog.get_logger()


@tool
def hunter_lookup(domain: str) -> dict:
    """
    Look up company information and email patterns for a domain using Hunter.io.

    Args:
        domain: Company website domain (e.g., 'acmecorp.com')

    Returns:
        Company info including organization name, email pattern, and contacts
    """
    if not settings.hunter_api_key:
        logger.warning("hunter_lookup skipped: no API key configured")
        return {}

    try:
        response = httpx.get(
            "https://api.hunter.io/v2/domain-search",
            params={
                "domain": domain,
                "api_key": settings.hunter_api_key,
            },
            timeout=settings.tool_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json().get("data", {})

        organization = data.get("organization", "")
        country = data.get("country", "")
        city = data.get("city", "")
        company_size_raw = data.get("company_size", "")
        employee_count = _parse_employee_count(company_size_raw)

        location_parts = [p for p in [city, country] if p]
        location = ", ".join(location_parts) if location_parts else ""

        result = {
            "domain": data.get("domain", domain),
            "organization": organization,
            "company_name": organization or "",
            "country": country,
            "state": data.get("state", ""),
            "city": city,
            "location": location,
            "email_count": data.get("emails", []),
            "pattern": data.get("pattern", ""),
            "industry": data.get("industry", ""),
            "company_size": company_size_raw,
            "employee_count": employee_count,
        }

        logger.info("hunter_lookup completed", domain=domain)
        return result

    except Exception as e:
        logger.error("hunter_lookup failed", domain=domain, error=str(e))
        raise


def _parse_employee_count(size_str: str) -> int | None:
    """Parse Hunter's company_size string (e.g. '50-200', '1-10') into a midpoint integer."""
    if not size_str:
        return None
    try:
        parts = str(size_str).replace(",", "").split("-")
        nums = [int(p.strip()) for p in parts if p.strip().isdigit()]
        if len(nums) == 2:
            return (nums[0] + nums[1]) // 2
        if len(nums) == 1:
            return nums[0]
    except Exception:
        pass
    return None
