import httpx
import structlog
from strands import tool

from config import settings

logger = structlog.get_logger()


@tool
def clearbit_enrich(domain: str) -> dict:
    """
    Enrich company data using Clearbit's company lookup API.
    Returns employee count, industry, estimated revenue, location, description, and tech stack.

    Args:
        domain: Company website domain (e.g., 'acmecorp.com')

    Returns:
        Enriched company profile with firmographic data
    """
    if not settings.clearbit_api_key:
        logger.warning("clearbit_enrich skipped: no API key configured")
        return {}

    try:
        response = httpx.get(
            "https://company.clearbit.com/v2/companies/find",
            params={"domain": domain},
            headers={"Authorization": f"Bearer {settings.clearbit_api_key}"},
            timeout=settings.tool_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()

        metrics = data.get("metrics", {})
        geo = data.get("geo", {})
        category = data.get("category", {})

        location_parts = [p for p in [geo.get("city"), geo.get("stateCode"), geo.get("country")] if p]
        location = ", ".join(location_parts)

        employee_count = metrics.get("employees") or metrics.get("employeesRange")
        if isinstance(employee_count, str):
            employee_count = _parse_range(employee_count)

        estimated_revenue = metrics.get("estimatedAnnualRevenue")
        if isinstance(estimated_revenue, str):
            estimated_revenue = _parse_revenue(estimated_revenue)

        result = {
            "company_name": data.get("name", ""),
            "domain": data.get("domain", domain),
            "industry": category.get("industry") or category.get("sector") or "",
            "employee_count": employee_count if isinstance(employee_count, int) else None,
            "estimated_revenue": estimated_revenue,
            "location": location,
            "description": data.get("description", ""),
            "tech_stack": [t.get("tag", "") for t in data.get("tech", []) if t.get("tag")],
            "funding_stage": data.get("crunchbaseFundingTotal", {}).get("currency", "") if isinstance(data.get("crunchbaseFundingTotal"), dict) else "",
            "founded_year": data.get("foundedYear"),
            "linkedin_url": data.get("linkedin", {}).get("handle", "") if isinstance(data.get("linkedin"), dict) else "",
        }

        logger.info("clearbit_enrich completed", domain=domain, employees=result["employee_count"])
        return result

    except Exception as e:
        logger.error("clearbit_enrich failed", domain=domain, error=str(e))
        raise


def _parse_range(range_str: str) -> int | None:
    """Parse employee range string like '51-200' into midpoint."""
    try:
        parts = range_str.replace(",", "").split("-")
        nums = [int(p.strip()) for p in parts if p.strip().isdigit()]
        if len(nums) == 2:
            return (nums[0] + nums[1]) // 2
        if len(nums) == 1:
            return nums[0]
    except Exception:
        pass
    return None


def _parse_revenue(rev_str: str) -> int | None:
    """Parse Clearbit revenue string like '$1M-$10M' into midpoint integer."""
    import re
    if not rev_str:
        return None
    try:
        multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
        nums = re.findall(r"\$?([\d.]+)([KMB]?)", rev_str.upper())
        values = []
        for num, suffix in nums:
            val = float(num) * multipliers.get(suffix, 1)
            values.append(int(val))
        if len(values) == 2:
            return (values[0] + values[1]) // 2
        if len(values) == 1:
            return values[0]
    except Exception:
        pass
    return None
