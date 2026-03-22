"""Government business registry tools for verified company discovery.

UK Companies House API — free with API key (register at developer.company-information.service.gov.uk).
Returns verified company data: name, status, incorporation date,
registered address, officers (directors/secretaries).
"""

import logging

from strands import tool

from app.config import get_settings
from app.tools.retry_utils import httpx_get_with_retry

logger = logging.getLogger(__name__)

COMPANIES_HOUSE_API = "https://api.company-information.service.gov.uk"


def _get_companies_house_auth() -> tuple[str, str] | None:
    """Get Companies House API key as HTTP Basic Auth tuple, or None if not configured."""
    settings = get_settings()
    key = settings.COMPANIES_HOUSE_API_KEY
    if key:
        return (key, "")  # API key as username, empty password (Basic Auth)
    return None


@tool
def search_uk_companies(
    query: str,
    items_per_page: int = 50,
    start_index: int = 0,
) -> dict:
    """
    Search the UK Companies House registry for companies by name or keyword.
    FREE, no API key required. Returns legally verified company data.

    Useful for UK-based company discovery, verification of company details,
    and officer (director/secretary) names for contact discovery.

    USE IN STAGES: Stage 1 (Discovery) for UK companies,
    Stage 4 (Contacts) via get_uk_company_officers for director names.

    Args:
        query: Company name or keyword to search for
        items_per_page: Results per page (max 100)
        start_index: Pagination start index

    Returns:
        dict with 'companies' list containing name, company_number,
        status, incorporation_date, address, and type
    """
    try:
        auth = _get_companies_house_auth()
        response = httpx_get_with_retry(
            f"{COMPANIES_HOUSE_API}/search/companies",
            params={
                "q": query,
                "items_per_page": min(items_per_page, 100),
                "start_index": start_index,
            },
            headers={"Accept": "application/json"},
            auth=auth,
            timeout=20,
        )

        if response.status_code in (401, 403):
            return {
                "error": "UK Companies House API key missing or invalid. "
                "Set COMPANIES_HOUSE_API_KEY in .env (free at developer.company-information.service.gov.uk). "
                "Do NOT retry — use search_wikidata_companies or exa_search instead.",
                "companies": [],
            }

        if response.status_code != 200:
            return {
                "error": f"Companies House API returned HTTP {response.status_code}",
                "companies": [],
            }

        data = response.json()
        companies = []

        for item in data.get("items", []):
            address = item.get("address", {})
            companies.append({
                "name": item.get("title", ""),
                "company_number": item.get("company_number", ""),
                "status": item.get("company_status", ""),
                "type": item.get("company_type", ""),
                "incorporation_date": item.get("date_of_creation", ""),
                "address": {
                    "line1": address.get("address_line_1", ""),
                    "line2": address.get("address_line_2", ""),
                    "locality": address.get("locality", ""),
                    "region": address.get("region", ""),
                    "postal_code": address.get("postal_code", ""),
                    "country": address.get("country", "United Kingdom"),
                },
                "sic_codes": item.get("sic_codes", []),
                "source": "uk_companies_house",
            })

        logger.info(
            f"UK Companies House: found {len(companies)} companies for query='{query}'"
        )

        return {
            "companies": companies,
            "total_results": data.get("total_results", 0),
            "returned": len(companies),
        }

    except Exception as e:
        logger.error(f"UK Companies House search failed: {e}")
        return {"error": str(e), "companies": []}


@tool
def get_uk_company_officers(
    company_number: str,
    items_per_page: int = 50,
) -> dict:
    """
    Get officers (directors, secretaries) for a UK company by company number.
    FREE, no API key required. Returns legally verified officer names.

    Useful for Stage 4 (Contact Discovery) — officer names are verified contacts.

    Args:
        company_number: UK Companies House company number (e.g. "00445790")
        items_per_page: Results per page (max 100)

    Returns:
        dict with 'officers' list containing name, role, appointed_on, nationality
    """
    try:
        auth = _get_companies_house_auth()
        response = httpx_get_with_retry(
            f"{COMPANIES_HOUSE_API}/company/{company_number}/officers",
            params={"items_per_page": min(items_per_page, 100)},
            headers={"Accept": "application/json"},
            auth=auth,
            timeout=15,
        )

        if response.status_code in (401, 403):
            return {
                "error": "UK Companies House API key missing or invalid. "
                "Set COMPANIES_HOUSE_API_KEY in .env (free at developer.company-information.service.gov.uk). "
                "Do NOT retry — use find_company_executives instead.",
                "officers": [],
            }

        if response.status_code != 200:
            return {
                "error": f"Companies House API returned HTTP {response.status_code}",
                "officers": [],
            }

        data = response.json()
        officers = []

        for item in data.get("items", []):
            # Skip resigned officers
            if item.get("resigned_on"):
                continue

            officers.append({
                "name": item.get("name", ""),
                "role": item.get("officer_role", ""),
                "appointed_on": item.get("appointed_on", ""),
                "nationality": item.get("nationality", ""),
                "occupation": item.get("occupation", ""),
                "country_of_residence": item.get("country_of_residence", ""),
            })

        logger.info(
            f"UK Companies House: found {len(officers)} active officers "
            f"for company {company_number}"
        )

        return {
            "officers": officers,
            "company_number": company_number,
            "total_active": len(officers),
        }

    except Exception as e:
        logger.error(f"UK Companies House officers lookup failed: {e}")
        return {"error": str(e), "officers": []}
