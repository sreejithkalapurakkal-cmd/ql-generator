"""OpenCorporates company search tool.

Searches the OpenCorporates API (200M+ companies worldwide, free tier
200 req/day, no API key required). Returns company name, jurisdiction,
incorporation date, status, registered address, and officers (directors).

Officers data provides legally verified contact names for Stage 4.
"""

import logging
from urllib.parse import quote_plus

from strands import tool

from app.tools.retry_utils import httpx_get_with_retry

logger = logging.getLogger(__name__)

OC_BASE_URL = "https://api.opencorporates.com/v0.4"

# Map country names to OpenCorporates jurisdiction codes
COUNTRY_TO_JURISDICTION = {
    "usa": "us", "united states": "us", "us": "us",
    "uk": "gb", "united kingdom": "gb", "great britain": "gb",
    "germany": "de", "deutschland": "de",
    "france": "fr",
    "canada": "ca",
    "australia": "au",
    "japan": "jp",
    "india": "in",
    "china": "cn",
    "south korea": "kr", "korea": "kr",
    "brazil": "br",
    "israel": "il",
    "switzerland": "ch",
    "netherlands": "nl",
    "sweden": "se",
    "singapore": "sg",
    "ireland": "ie",
    "italy": "it",
    "spain": "es",
    "norway": "no",
    "denmark": "dk",
    "finland": "fi",
    "austria": "at",
    "belgium": "be",
    "new zealand": "nz",
    "mexico": "mx",
    "uae": "ae", "united arab emirates": "ae",
    "poland": "pl",
    "hong kong": "hk",
    "taiwan": "tw",
}


def _get_jurisdiction(country: str) -> str | None:
    """Map a country name to an OpenCorporates jurisdiction code."""
    return COUNTRY_TO_JURISDICTION.get(country.lower().strip())


@tool
def search_opencorporates(
    query: str,
    country: str = "",
    industry_keywords: list[str] = None,
    per_page: int = 50,
) -> dict:
    """
    Search OpenCorporates for companies by name, industry keywords, and country.
    FREE, no API key required (200 requests/day limit).
    Contains 200M+ companies worldwide with official registry data.

    Returns: company name, jurisdiction, incorporation date, company status,
    registered address, and officer names (directors/secretaries).

    Officer data provides LEGALLY VERIFIED contact names useful in Stage 4.

    USE IN STAGES: Stage 1 (Industry Discovery) for geography-specific ICPs,
    Stage 4 (Contact Discovery) for officer/director names.

    Args:
        query: Company name or industry keyword to search for
        country: Optional country name to filter results (e.g. "UK", "Germany")
        industry_keywords: Optional list of industry terms to refine search
        per_page: Number of results per page (max 100)

    Returns:
        dict with 'companies' list, 'total_found', and 'pagination' info
    """
    industry_keywords = industry_keywords or []

    # Build search URL
    params = {
        "q": query,
        "per_page": min(per_page, 100),
        "order": "score",
    }

    # Add jurisdiction filter
    if country:
        jurisdiction = _get_jurisdiction(country)
        if jurisdiction:
            params["jurisdiction_code"] = jurisdiction

    # Add industry filter via company_type if available
    if industry_keywords:
        # Append industry keywords to query for better results
        combined_query = f"{query} {' '.join(industry_keywords[:2])}"
        params["q"] = combined_query

    try:
        response = httpx_get_with_retry(
            f"{OC_BASE_URL}/companies/search",
            params=params,
            headers={"User-Agent": "qlGen/1.0 (Lead Generation Research Tool)"},
            timeout=20,
        )

        if response.status_code == 429:
            return {
                "error": "RATE_LIMITED: OpenCorporates daily limit reached (200/day). Try again tomorrow.",
                "companies": [],
                "total_found": 0,
                "rate_limited": True,
            }

        if response.status_code in (401, 403):
            return {
                "error": "OpenCorporates API requires authentication. "
                "Do NOT retry — use search_wikidata_companies (free, no key) instead.",
                "companies": [],
                "total_found": 0,
            }

        if response.status_code != 200:
            return {
                "error": f"OpenCorporates returned HTTP {response.status_code}",
                "companies": [],
                "total_found": 0,
            }

        data = response.json()
        api_result = data.get("results", {})
        raw_companies = api_result.get("companies", [])
        total_count = api_result.get("total_count", 0)

        companies = []
        for item in raw_companies:
            company_data = item.get("company", {})

            name = company_data.get("name", "")
            jurisdiction = company_data.get("jurisdiction_code", "")
            incorporation_date = company_data.get("incorporation_date", "")
            status = company_data.get("current_status", "")
            company_type = company_data.get("company_type", "")
            registered_address = company_data.get("registered_address_in_full", "")
            oc_url = company_data.get("opencorporates_url", "")
            company_number = company_data.get("company_number", "")

            # Extract officers if available
            officers = []
            for officer_item in company_data.get("officers", []):
                officer = officer_item.get("officer", {})
                officers.append({
                    "name": officer.get("name", ""),
                    "position": officer.get("position", ""),
                    "start_date": officer.get("start_date", ""),
                    "end_date": officer.get("end_date"),
                })

            companies.append({
                "name": name,
                "jurisdiction": jurisdiction,
                "incorporation_date": incorporation_date,
                "status": status,
                "company_type": company_type,
                "registered_address": registered_address,
                "company_number": company_number,
                "officers": officers[:10],  # Cap officers per company
                "source": "opencorporates",
                "opencorporates_url": oc_url,
            })

        # Filter to active companies only
        active_companies = [
            c for c in companies
            if c.get("status", "").lower() in ("active", "live", "open", "")
            or not c.get("status")
        ]

        logger.info(
            f"OpenCorporates: found {len(active_companies)} active companies "
            f"(of {total_count} total) for query='{query}'"
        )

        return {
            "companies": active_companies,
            "total_found": len(active_companies),
            "total_in_registry": total_count,
            "query_info": {
                "query": query,
                "country": country,
                "jurisdiction": _get_jurisdiction(country) if country else None,
            },
        }

    except Exception as e:
        logger.error(f"OpenCorporates search failed: {e}")
        return {
            "error": str(e),
            "companies": [],
            "total_found": 0,
        }


@tool
def get_opencorporates_officers(
    company_name: str,
    jurisdiction: str = "",
) -> dict:
    """
    Look up officers (directors, secretaries) for a specific company.
    FREE, no API key required. Returns legally verified contact names
    from official company registries.

    USE IN STAGES: Stage 4 (Contact Discovery) for verified decision-maker names.

    Args:
        company_name: Name of the company to look up
        jurisdiction: Two-letter jurisdiction code (e.g. "gb", "us_de", "de")

    Returns:
        dict with 'officers' list and company details
    """
    params = {
        "q": company_name,
        "per_page": 5,
    }
    if jurisdiction:
        params["jurisdiction_code"] = jurisdiction

    try:
        # First find the company
        response = httpx_get_with_retry(
            f"{OC_BASE_URL}/companies/search",
            params=params,
            headers={"User-Agent": "qlGen/1.0 (Lead Generation Research Tool)"},
            timeout=20,
        )

        if response.status_code in (401, 403):
            return {
                "error": "OpenCorporates API requires authentication. "
                "Do NOT retry — use search_wikidata_companies instead.",
                "officers": [],
            }
        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}", "officers": []}

        data = response.json()
        raw_companies = data.get("results", {}).get("companies", [])
        if not raw_companies:
            return {"error": "Company not found", "officers": []}

        # Get the first matching company's officers
        best_match = raw_companies[0].get("company", {})
        oc_url = best_match.get("opencorporates_url", "")

        # Fetch officers via the officers endpoint
        jurisdiction_code = best_match.get("jurisdiction_code", "")
        company_number = best_match.get("company_number", "")

        if not jurisdiction_code or not company_number:
            return {
                "company_name": best_match.get("name", ""),
                "officers": best_match.get("officers", []),
            }

        officers_response = httpx_get_with_retry(
            f"{OC_BASE_URL}/companies/{jurisdiction_code}/{company_number}/officers",
            headers={"User-Agent": "qlGen/1.0 (Lead Generation Research Tool)"},
            timeout=20,
        )

        officers = []
        if officers_response.status_code == 200:
            officers_data = officers_response.json()
            for item in officers_data.get("results", {}).get("officers", []):
                officer = item.get("officer", {})
                # Only include current officers (no end_date)
                if not officer.get("end_date"):
                    officers.append({
                        "name": officer.get("name", ""),
                        "position": officer.get("position", ""),
                        "start_date": officer.get("start_date", ""),
                    })

        return {
            "company_name": best_match.get("name", ""),
            "jurisdiction": jurisdiction_code,
            "company_number": company_number,
            "officers": officers[:15],
            "total_officers": len(officers),
            "opencorporates_url": oc_url,
        }

    except Exception as e:
        logger.error(f"OpenCorporates officer lookup failed: {e}")
        return {"error": str(e), "officers": []}
