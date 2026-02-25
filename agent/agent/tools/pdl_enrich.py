import httpx
import structlog
from strands import tool

from config import settings

logger = structlog.get_logger()


@tool
def pdl_enrich(domain: str) -> dict:
    """
    Enrich company data using People Data Labs (PDL) company enrichment API.
    Returns employee count, industry, revenue, location, and founding year.

    Args:
        domain: Company website domain (e.g., 'acmecorp.com')

    Returns:
        Enriched company profile with firmographic data
    """
    if not settings.pdl_api_key:
        logger.warning("pdl_enrich skipped: no API key configured")
        return {}

    try:
        response = httpx.get(
            "https://api.peopledatalabs.com/v5/company/enrich",
            params={"website": domain},
            headers={
                "X-Api-Key": settings.pdl_api_key,
                "Accept": "application/json",
            },
            timeout=settings.tool_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()

        location_parts = [p for p in [
            data.get("location", {}).get("locality") if isinstance(data.get("location"), dict) else None,
            data.get("location", {}).get("region") if isinstance(data.get("location"), dict) else None,
            data.get("location", {}).get("country") if isinstance(data.get("location"), dict) else None,
        ] if p]
        location = ", ".join(location_parts)

        employee_count = data.get("employee_count")
        if not employee_count:
            size_range = data.get("size", "")
            employee_count = _parse_size(size_range)

        result = {
            "company_name": data.get("name", ""),
            "domain": data.get("website", domain),
            "industry": data.get("industry", "") or data.get("tags", [""])[0] if data.get("tags") else "",
            "employee_count": employee_count,
            "estimated_revenue": _parse_revenue_range(data.get("inferred_revenue", "")),
            "location": location,
            "description": data.get("summary", ""),
            "tech_stack": data.get("tech_stack", []),
            "founded_year": data.get("founded", {}).get("year") if isinstance(data.get("founded"), dict) else data.get("founded"),
            "linkedin_url": data.get("linkedin_url", ""),
            "total_funding": data.get("total_funding_raised"),
        }

        logger.info("pdl_enrich completed", domain=domain, employees=result["employee_count"])
        return result

    except Exception as e:
        logger.error("pdl_enrich failed", domain=domain, error=str(e))
        raise


def _parse_size(size_str: str) -> int | None:
    """Parse PDL size string like '51-200' or 'medium' into an integer."""
    if not size_str:
        return None
    size_map = {
        "1-10": 5, "11-50": 30, "51-200": 125,
        "201-500": 350, "501-1000": 750, "1001-5000": 3000,
        "5001-10000": 7500, "10001+": 15000,
        "small": 25, "medium": 125, "large": 750,
    }
    if size_str in size_map:
        return size_map[size_str]
    try:
        import re
        parts = re.findall(r"\d+", size_str.replace(",", ""))
        nums = [int(p) for p in parts]
        if len(nums) == 2:
            return (nums[0] + nums[1]) // 2
        if len(nums) == 1:
            return nums[0]
    except Exception:
        pass
    return None


def _parse_revenue_range(rev_str: str) -> int | None:
    """Parse PDL revenue string like '$1M-$10M' into midpoint integer."""
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
