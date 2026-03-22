"""French company registry tool — Recherche Entreprises API.

Wraps the French government's official open company search API (SIRENE data).
FREE, no authentication required. ~12M French business entities.
Returns employee counts, revenue, directors, industry codes, and addresses.
"""

import logging

from strands import tool

from app.tools.retry_utils import httpx_get_with_retry

logger = logging.getLogger(__name__)

API_BASE = "https://recherche-entreprises.api.gouv.fr"

# French employee range codes → midpoint estimates
_TRANCHE_EFFECTIF_MAP = {
    "00": 0,      # 0 employees
    "01": 1,      # 1-2
    "02": 3,      # 3-5
    "03": 8,      # 6-9
    "11": 15,     # 10-19
    "12": 35,     # 20-49
    "21": 75,     # 50-99
    "22": 150,    # 100-199
    "31": 350,    # 200-499
    "32": 750,    # 500-999
    "41": 1500,   # 1000-1999
    "42": 3500,   # 2000-4999
    "51": 7500,   # 5000-9999
    "52": 15000,  # 10000+
    "53": 15000,  # 10000+
}

# Map min_employees → minimum tranche code for filtering
_EMPLOYEE_MIN_TO_TRANCHE = [
    (5000, "51"),
    (2000, "42"),
    (1000, "41"),
    (500, "32"),
    (200, "31"),
    (100, "22"),
    (50, "21"),
    (20, "12"),
    (10, "11"),
    (3, "02"),
    (1, "01"),
]


def _estimate_employees(tranche_code: str) -> int | None:
    """Convert French employee range code to midpoint estimate."""
    if not tranche_code:
        return None
    return _TRANCHE_EFFECTIF_MAP.get(tranche_code)


def _parse_company(item: dict) -> dict:
    """Parse a single company from the API response."""
    siege = item.get("siege", {})
    dirigeants = item.get("dirigeants", [])
    complements = item.get("complements", {})

    # Employee count from tranche code
    tranche = item.get("tranche_effectif_salarie")
    employee_count = _estimate_employees(tranche)

    # Directors
    directors = []
    for d in dirigeants[:10]:
        name_parts = []
        if d.get("prenom"):
            name_parts.append(d["prenom"])
        if d.get("nom"):
            name_parts.append(d["nom"])
        if name_parts:
            directors.append({
                "name": " ".join(name_parts),
                "role": d.get("qualite", ""),
                "nationality": d.get("nationalite", ""),
            })

    # City from siege
    city = siege.get("libelle_commune", "") or siege.get("commune", "")

    # Industry description
    activite = item.get("activite_principale", "")
    section = item.get("section_activite_principale", "")

    return {
        "name": item.get("nom_complet", "") or item.get("nom_raison_sociale", ""),
        "website": "",  # Not provided by this API
        "industry": section,
        "sub_industry": activite,
        "country": "France",
        "city": city,
        "employee_count": employee_count,
        "revenue_estimate": None,
        "description": f"{item.get('nature_juridique', '')} — {activite}".strip(" —"),
        "directors": directors,
        "source": "french_registry",
        "siren": item.get("siren", ""),
        "siret": siege.get("siret", ""),
    }


@tool
def search_french_companies(
    query: str,
    min_employees: int = None,
    max_employees: int = None,
    limit: int = 25,
) -> dict:
    """
    Search the French government company registry (SIRENE / Recherche Entreprises).
    FREE, no API key required. Contains ~12M French business entities.

    Returns company name, employee count estimate, industry codes (NAF/APE),
    directors (names + roles), registered address, and SIREN/SIRET identifiers.

    BEST FOR: Finding French companies by industry and size. Rich structured data.
    USE IN STAGE: Company Discovery (Stage 1) when ICP targets France.

    Args:
        query: Company name or industry keyword (e.g., "medical device", "dispositif médical")
        min_employees: Minimum employee count filter (approximate — uses ranges)
        max_employees: Maximum employee count filter (approximate — uses ranges)
        limit: Maximum results to return (default 25, max 25 per page)

    Returns:
        dict with 'companies' list, 'total_found', and 'source'
    """
    params = {
        "q": query,
        "per_page": min(limit, 25),
        "page": 1,
        "etat_administratif": "A",  # Active companies only
    }

    # Map employee range to tranche filter
    if min_employees:
        for threshold, code in _EMPLOYEE_MIN_TO_TRANCHE:
            if min_employees >= threshold:
                params["tranche_effectif_salarie_entreprise"] = code
                break

    try:
        response = httpx_get_with_retry(
            f"{API_BASE}/search",
            params=params,
            headers={
                "Accept": "application/json",
                "User-Agent": "qlGen/1.0 (Lead Generation Research Tool)",
            },
            timeout=20,
        )

        if response.status_code != 200:
            return {
                "error": f"French registry returned HTTP {response.status_code}",
                "companies": [],
                "total_found": 0,
            }

        data = response.json()
        results = data.get("results", [])
        total = data.get("total_results", 0)

        companies = []
        for item in results:
            parsed = _parse_company(item)

            # Client-side employee filter (API filter is approximate)
            if max_employees and parsed["employee_count"] and parsed["employee_count"] > max_employees * 2:
                continue
            if min_employees and parsed["employee_count"] and parsed["employee_count"] < min_employees * 0.3:
                continue

            if parsed["name"]:
                companies.append(parsed)

        logger.info(f"French registry: found {len(companies)} companies (total: {total}) for query '{query}'")

        return {
            "companies": companies,
            "total_found": total,
            "returned": len(companies),
            "source": "recherche-entreprises.api.gouv.fr",
        }

    except Exception as e:
        logger.error(f"French registry search failed: {e}")
        return {
            "error": str(e),
            "companies": [],
            "total_found": 0,
        }
