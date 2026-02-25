import httpx
import structlog
from strands import tool

from config import settings

logger = structlog.get_logger()


@tool
def apollo_enrich(domain: str) -> dict:
    """
    Enrich company data using Apollo.io's company enrichment API.

    Args:
        domain: Company website domain (e.g., 'acmecorp.com')

    Returns:
        Enriched company profile with firmographic data
    """
    if not settings.apollo_api_key:
        logger.warning("apollo_enrich skipped: no API key configured")
        return {}

    try:
        response = httpx.post(
            "https://api.apollo.io/api/v1/organizations/enrich",
            headers={
                "Content-Type": "application/json",
                "x-api-key": settings.apollo_api_key,
            },
            json={"domain": domain},
            timeout=settings.tool_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json().get("organization", {})

        result = {
            "company_name": data.get("name", ""),
            "domain": data.get("primary_domain", domain),
            "industry": data.get("industry", ""),
            "employee_count": data.get("estimated_num_employees"),
            "annual_revenue": data.get("annual_revenue"),
            "location": _build_location(data),
            "description": data.get("short_description", ""),
            "tech_stack": data.get("technology_names", []),
            "funding_stage": data.get("latest_funding_stage", ""),
            "total_funding": data.get("total_funding"),
            "founded_year": data.get("founded_year"),
            "linkedin_url": data.get("linkedin_url", ""),
        }

        logger.info("apollo_enrich completed", domain=domain)
        return result

    except Exception as e:
        logger.error("apollo_enrich failed", domain=domain, error=str(e))
        raise


def _build_location(data: dict) -> str:
    parts = []
    if data.get("city"):
        parts.append(data["city"])
    if data.get("state"):
        parts.append(data["state"])
    if data.get("country"):
        parts.append(data["country"])
    return ", ".join(parts)
