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

        result = {
            "domain": data.get("domain", domain),
            "organization": data.get("organization", ""),
            "country": data.get("country", ""),
            "state": data.get("state", ""),
            "city": data.get("city", ""),
            "email_count": data.get("emails", []),
            "pattern": data.get("pattern", ""),
            "industry": data.get("industry", ""),
            "company_size": data.get("company_size", ""),
        }

        logger.info("hunter_lookup completed", domain=domain)
        return result

    except Exception as e:
        logger.error("hunter_lookup failed", domain=domain, error=str(e))
        raise
