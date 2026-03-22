"""USPTO PatentsView API tool for patent-based company discovery.

Queries the PatentsView API to find companies by technology area.
Completely free, no API key required. Patent activity is a strong
budget signal (R&D investment) and useful for discovery in
tech/manufacturing/pharma industries.
"""

import logging
import json

from strands import tool

from app.tools.retry_utils import httpx_post_with_retry, httpx_get_with_retry

logger = logging.getLogger(__name__)

PATENTSVIEW_API = "https://api.patentsview.org/patents/query"


@tool
def search_patents_by_technology(
    technology_keywords: list[str],
    assignee_country: str = "",
    years_back: int = 3,
    min_patents: int = 2,
    max_results: int = 100,
) -> dict:
    """
    Search USPTO patents by technology area to discover innovative companies.
    FREE, no API key required.

    Patent activity indicates R&D investment (budget signal) and innovation.
    Companies filing patents are actively investing in technology.

    USE IN STAGES: Stage 1 (Discovery) for tech/manufacturing/pharma companies,
    Stage 3 (Signals) for R&D investment evidence.

    Args:
        technology_keywords: Technology terms to search in patent titles/abstracts
            (e.g. ["medical device", "wearable sensor", "connected health"])
        assignee_country: Optional country filter (e.g. "US", "DE", "GB")
        years_back: How many years of patents to search (default 3)
        min_patents: Minimum patent count to include a company (default 2)
        max_results: Maximum number of companies to return

    Returns:
        dict with 'companies' list (sorted by patent count), 'total_patents',
        and 'technology_areas'
    """
    from datetime import datetime

    current_year = datetime.now().year
    start_year = current_year - years_back

    # Build query
    keyword_clauses = []
    for kw in technology_keywords[:5]:  # Limit keywords to avoid overly complex query
        keyword_clauses.append({"_text_any": {"patent_title": kw}})
        keyword_clauses.append({"_text_any": {"patent_abstract": kw}})

    query_filter = {
        "_and": [
            {"_or": keyword_clauses},
            {"_gte": {"patent_date": f"{start_year}-01-01"}},
        ]
    }

    if assignee_country:
        query_filter["_and"].append(
            {"assignee_country": assignee_country.upper()}
        )

    request_body = {
        "q": json.dumps(query_filter),
        "f": json.dumps([
            "patent_number", "patent_title", "patent_date",
            "assignee_organization", "assignee_country",
            "assignee_city", "assignee_state",
        ]),
        "o": json.dumps({"per_page": 1000}),
    }

    try:
        response = httpx_get_with_retry(
            PATENTSVIEW_API,
            params=request_body,
            headers={"User-Agent": "qlGen/1.0 (Lead Generation Research Tool)"},
            timeout=30,
        )

        if response.status_code != 200:
            return {
                "error": f"PatentsView API returned HTTP {response.status_code}",
                "companies": [],
                "total_patents": 0,
            }

        data = response.json()
        patents = data.get("patents", [])

        if not patents:
            return {
                "companies": [],
                "total_patents": 0,
                "message": f"No patents found for keywords: {technology_keywords}",
            }

        # Aggregate by assignee organization
        companies: dict[str, dict] = {}
        for patent in patents:
            assignees = patent.get("assignees", [])
            for assignee in assignees:
                org = assignee.get("assignee_organization", "")
                if not org or len(org) < 3:
                    continue

                org_key = org.lower().strip()
                if org_key not in companies:
                    companies[org_key] = {
                        "name": org,
                        "country": assignee.get("assignee_country", ""),
                        "state": assignee.get("assignee_state", ""),
                        "city": assignee.get("assignee_city", ""),
                        "patent_count": 0,
                        "recent_patents": [],
                        "technology_areas": set(),
                        "source": "uspto_patents",
                    }

                companies[org_key]["patent_count"] += 1
                if len(companies[org_key]["recent_patents"]) < 5:
                    companies[org_key]["recent_patents"].append({
                        "number": patent.get("patent_number", ""),
                        "title": patent.get("patent_title", ""),
                        "date": patent.get("patent_date", ""),
                    })
                # Extract tech area from title
                title = patent.get("patent_title", "").lower()
                for kw in technology_keywords:
                    if kw.lower() in title:
                        companies[org_key]["technology_areas"].add(kw)

        # Filter by minimum patents and convert sets to lists
        filtered = []
        for comp in companies.values():
            if comp["patent_count"] >= min_patents:
                comp["technology_areas"] = sorted(comp["technology_areas"])
                filtered.append(comp)

        # Sort by patent count (most innovative first)
        filtered.sort(key=lambda c: c["patent_count"], reverse=True)
        filtered = filtered[:max_results]

        logger.info(
            f"USPTO Patents: found {len(filtered)} companies with {min_patents}+ patents "
            f"for keywords={technology_keywords}"
        )

        return {
            "companies": filtered,
            "total_patents": len(patents),
            "total_companies_with_min_patents": len(filtered),
            "search_info": {
                "keywords": technology_keywords,
                "country": assignee_country,
                "date_range": f"{start_year}-{current_year}",
            },
        }

    except Exception as e:
        logger.error(f"USPTO patent search failed: {e}")
        return {
            "error": str(e),
            "companies": [],
            "total_patents": 0,
        }
