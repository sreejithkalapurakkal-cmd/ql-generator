import httpx
import structlog
from strands import tool

from config import settings

logger = structlog.get_logger()


@tool
def lusha_enrich(company_name: str, domain: str = "") -> dict:
    """
    Enrich company data with firmographic details using Lusha.

    Args:
        company_name: Name of the company
        domain: Optional domain for more precise matching

    Returns:
        Company profile with employee count, revenue, industry, location
    """
    if not settings.lusha_api_key:
        logger.warning("lusha_enrich skipped: no API key configured")
        return {}

    try:
        params = {"company_name": company_name}
        if domain:
            params["domain"] = domain

        response = httpx.get(
            "https://api.lusha.com/company",
            headers={
                "api_key": settings.lusha_api_key,
            },
            params=params,
            timeout=settings.tool_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()

        result = {
            "company_name": data.get("company_name", company_name),
            "domain": data.get("domain", domain),
            "industry": data.get("industry", ""),
            "employee_count": data.get("employee_count"),
            "revenue": data.get("revenue"),
            "location": data.get("location", ""),
            "description": data.get("description", ""),
            "founded_year": data.get("founded_year"),
        }

        logger.info("lusha_enrich completed", company=company_name)
        return result

    except Exception as e:
        logger.error("lusha_enrich failed", company=company_name, error=str(e))
        raise
