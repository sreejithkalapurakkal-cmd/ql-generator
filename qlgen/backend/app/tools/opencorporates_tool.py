import httpx
from strands import tool


@tool
def get_company_registry(
    company_name: str,
    country: str = "us",
) -> dict:
    """
    Look up company legal registration data from OpenCorporates. FREE (basic tier).
    Covers 140+ countries. No API key needed for basic searches.
    BEST FOR: Verifying a company is legally active, finding incorporation date,
    jurisdiction, and registered directors/officers.
    USE IN STAGES: Company Discovery (Stage 1) for verification,
    BANT Scoring (Stage 4) for Authority dimension.

    Args:
        company_name: Legal company name (e.g. 'Stripe Inc', 'Acme Corp')
        country: ISO 2-letter country code (e.g. 'us', 'gb', 'de'). Default 'us'.

    Returns:
        dict with company_number, jurisdiction, incorporation_date,
        current_status, registered_officers
    """
    country_code = country.strip().lower()

    try:
        url = "https://api.opencorporates.com/v0.4/companies/search"
        params = {
            "q": company_name,
            "jurisdiction_code": country_code,
            "per_page": 5,
            "format": "json",
        }

        resp = httpx.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        companies = data.get("results", {}).get("companies", [])
        if not companies:
            return {
                "error": f"No company found for '{company_name}' in {country_code.upper()}",
                "companies": [],
            }

        results = []
        for entry in companies[:3]:
            c = entry.get("company", {})

            # Extract officers if available
            officers = []
            for officer in c.get("officers", [])[:5]:
                o = officer.get("officer", {})
                officers.append({
                    "name": o.get("name", ""),
                    "position": o.get("position", ""),
                    "start_date": o.get("start_date"),
                })

            results.append({
                "name": c.get("name", ""),
                "company_number": c.get("company_number", ""),
                "jurisdiction": c.get("jurisdiction_code", ""),
                "incorporation_date": c.get("incorporation_date"),
                "current_status": c.get("current_status", ""),
                "company_type": c.get("company_type", ""),
                "registered_address": c.get("registered_address_in_full", ""),
                "opencorporates_url": c.get("opencorporates_url", ""),
                "registered_officers": officers,
            })

        return {
            "query": company_name,
            "country": country_code,
            "companies": results,
        }

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            return {
                "error": "RATE_LIMITED: OpenCorporates free tier limit reached (500/month). "
                         "Use duckduckgo_search '[company] incorporation registration' "
                         "as an alternative.",
                "rate_limited": True,
                "companies": [],
            }
        return {"error": str(e), "companies": []}
    except Exception as e:
        return {"error": str(e), "companies": []}
