"""Nordic company registry tool — CVR API (cvrapi.dk).

Wraps the free Danish CVR API which covers Denmark, Norway, and Sweden.
FREE, no authentication required. Returns employee counts, industry codes,
contact info, and production unit details.
"""

import logging

from strands import tool

from app.tools.retry_utils import httpx_get_with_retry

logger = logging.getLogger(__name__)

API_BASE = "https://cvrapi.dk/api"

_COUNTRY_MAP = {
    "dk": "Denmark",
    "no": "Norway",
    "se": "Sweden",
    "denmark": "dk",
    "norway": "no",
    "sweden": "se",
}


def _normalize_country_code(country: str) -> str:
    """Normalize country input to 2-letter code."""
    c = country.lower().strip()
    if c in ("dk", "no", "se"):
        return c
    return _COUNTRY_MAP.get(c, "dk")


def _country_code_to_name(code: str) -> str:
    """Convert 2-letter code to country name."""
    return {"dk": "Denmark", "no": "Norway", "se": "Sweden"}.get(code, code)


def _parse_company(data: dict, country_code: str) -> dict:
    """Parse a single company from the CVR API response."""
    # Employee count
    employees = data.get("employees")
    employee_count = None
    if employees is not None:
        try:
            employee_count = int(employees)
        except (ValueError, TypeError):
            pass

    # Industry
    industry_desc = data.get("industrydesc", "")
    industry_code = data.get("industrycode", "")

    # Address
    city = data.get("city", "")
    address = data.get("address", "")
    zipcode = data.get("zipcode", "")

    return {
        "name": data.get("name", ""),
        "website": "",  # Not provided by this API
        "industry": industry_desc,
        "sub_industry": f"Code: {industry_code}" if industry_code else "",
        "country": _country_code_to_name(country_code),
        "city": city,
        "employee_count": employee_count,
        "revenue_estimate": None,
        "description": data.get("companydesc", "") or industry_desc,
        "email": data.get("email", ""),
        "phone": data.get("phone", ""),
        "source": "nordic_registry",
        "vat_number": str(data.get("vat", "")),
        "founded": data.get("startdate", ""),
        "address": f"{address}, {zipcode} {city}".strip(", "),
    }


@tool
def search_nordic_companies(
    query: str,
    country: str = "dk",
) -> dict:
    """
    Search the Nordic company registry (CVR API) for companies in Denmark, Norway, or Sweden.
    FREE, no API key required. Returns employee count, industry codes, contact info.

    BEST FOR: Looking up specific Nordic companies by name to get employee counts,
    industry codes, and contact details. Returns exact matches.
    USE IN STAGES: Company Discovery (Stage 1) for Nordic ICPs,
    Firmographic Fit (Stage 2) for verification of Nordic companies.

    Args:
        query: Company name or CVR/VAT number to search for
        country: Country code — "dk" (Denmark), "no" (Norway), or "se" (Sweden).
            Also accepts full names: "Denmark", "Norway", "Sweden".

    Returns:
        dict with 'companies' list (usually 1 exact match), 'total_found'
    """
    country_code = _normalize_country_code(country)

    try:
        response = httpx_get_with_retry(
            API_BASE,
            params={
                "search": query,
                "country": country_code,
            },
            headers={
                "Accept": "application/json",
                "User-Agent": "qlGen/1.0 (Lead Generation Research Tool) contact@qlgen.com",
            },
            timeout=15,
        )

        if response.status_code == 404:
            return {
                "companies": [],
                "total_found": 0,
                "message": f"No company found for '{query}' in {_country_code_to_name(country_code)}",
            }

        if response.status_code != 200:
            return {
                "error": f"Nordic registry returned HTTP {response.status_code}",
                "companies": [],
                "total_found": 0,
            }

        data = response.json()

        # API returns a single company object (not a list)
        if not data or not data.get("name"):
            return {
                "companies": [],
                "total_found": 0,
                "message": f"No company found for '{query}' in {_country_code_to_name(country_code)}",
            }

        company = _parse_company(data, country_code)
        logger.info(
            f"Nordic registry ({country_code}): found '{company['name']}' "
            f"(employees: {company['employee_count']}) for query '{query}'"
        )

        return {
            "companies": [company],
            "total_found": 1,
        }

    except Exception as e:
        logger.error(f"Nordic registry search failed: {e}")
        return {
            "error": str(e),
            "companies": [],
            "total_found": 0,
        }
