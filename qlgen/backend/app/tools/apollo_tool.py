import logging
import time
import httpx
from strands import tool
from app.config import get_settings
from app.tools.retry_utils import httpx_post_with_retry

logger = logging.getLogger(__name__)

RATE_LIMIT_CODES = {429, 402}

# Fields the discovery agent actually needs from Apollo org records.
# Dropping logo_url, languages, seo_description, raw LinkedIn data, etc.
_ORG_KEEP_FIELDS = {
    "name", "website_url", "industry", "city", "state", "country",
    "estimated_num_employees", "annual_revenue", "short_description",
}


def _trim_org(org: dict) -> dict:
    """Keep only fields the discovery agent needs to reduce context size."""
    trimmed = {k: org.get(k) for k in _ORG_KEEP_FIELDS}
    desc = trimmed.get("short_description") or ""
    trimmed["short_description"] = desc[:300]
    return trimmed

RATE_LIMIT_MSG = (
    "RATE_LIMITED: Apollo API quota exceeded. Do NOT retry this tool. "
    "Switch immediately to free alternatives: use exa_search, tavily_search, "
    "or duckduckgo_search for company discovery."
)


@tool
def apollo_company_search(
    query: str,
    industries: list[str] = None,
    locations: list[str] = None,
    min_employees: int = None,
    max_employees: int = None,
    revenue_range: list[str] = None,
    technology_names: list[str] = None,
    page: int = 1,
    per_page: int = 100,
) -> dict:
    """
    Search for companies using Apollo.io API.
    BEST FOR: Structured company database search with filters for industry,
    location, employee count, revenue range, and tech stack.
    USE IN STAGE: Company Discovery (Stage 1)

    IMPORTANT: The 'industries' parameter accepts freeform industry keywords
    (e.g., "medical devices", "healthcare technology"). These are merged into
    the keyword search — Apollo does not require internal tag IDs.

    Args:
        query: Search query describing the type of company (e.g., "medical device manufacturer")
        industries: Optional list of industry terms to add as keyword tags
            (e.g., ["medical devices", "healthcare technology"])
        locations: List of locations (cities, states, countries)
        min_employees: Minimum number of employees
        max_employees: Maximum number of employees
        revenue_range: Revenue filter ranges as strings.
            Valid values: "0,1000000", "1000000,10000000", "10000000,50000000",
            "50000000,100000000", "100000000,500000000", "500000000,1000000000",
            "1000000000,"
            Pass a list to match multiple ranges (e.g., ["1000000,10000000", "10000000,50000000"])
        technology_names: Filter by technology stack. Pass technology names as strings
            (e.g., ["salesforce", "aws", "react", "python"])
        page: Page number for pagination (start at 1, paginate through 1-5+)
        per_page: Results per page (max 100)

    Returns:
        dict with 'organizations' list and 'pagination' info
    """
    settings = get_settings()
    url = f"{settings.APOLLO_BASE_URL}/mixed_companies/search"
    headers = {
        "X-Api-Key": settings.APOLLO_API_KEY,
        "Content-Type": "application/json",
    }

    # Merge query + industries into keyword_tags (Apollo's freeform keyword field).
    # Do NOT use organization_industry_tag_ids — that requires Apollo's internal
    # numeric tag IDs and rejects freeform text with a 422 error.
    keyword_tags = []
    if query:
        keyword_tags.append(query)
    if industries:
        keyword_tags.extend(industries)

    payload = {
        "q_organization_keyword_tags": keyword_tags if keyword_tags else None,
        "organization_locations": locations,
        "organization_num_employees_ranges": (
            [f"{min_employees or ''},{max_employees or ''}"]
            if min_employees or max_employees
            else None
        ),
        "organization_revenue_ranges": revenue_range,
        "q_organization_technology_names": technology_names,
        "page": page,
        "per_page": min(per_page, 100),
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    logger.info(f"Apollo company search payload: {payload}")

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        # Trim org records to essential fields to prevent context window overflow
        if "organizations" in data:
            data["organizations"] = [_trim_org(o) for o in data["organizations"]]
        return data
    except httpx.HTTPStatusError as e:
        resp_body = ""
        try:
            resp_body = e.response.text[:500]
        except Exception:
            pass
        logger.warning(f"Apollo HTTP {e.response.status_code}: {resp_body}")

        if e.response.status_code in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True, "organizations": []}
        if e.response.status_code == 422:
            return {
                "error": (
                    f"Apollo rejected the request (422 Unprocessable Entity). "
                    f"Simplify the query — try fewer keywords or remove filters. "
                    f"Details: {resp_body}"
                ),
                "organizations": [],
            }
        if e.response.status_code in (401, 403):
            return {
                "error": f"Apollo authentication error ({e.response.status_code}). Check API key.",
                "organizations": [],
            }
        return {"error": str(e), "organizations": []}
    except Exception as e:
        return {"error": str(e), "organizations": []}


@tool
def apollo_company_search_paginated(
    query: str,
    industries: list[str] = None,
    locations: list[str] = None,
    min_employees: int = None,
    max_employees: int = None,
    revenue_range: list[str] = None,
    max_pages: int = 5,
    per_page: int = 25,
) -> dict:
    """
    Search for companies using Apollo.io with AUTO-PAGINATION across multiple pages.
    BEST FOR: Broad company discovery when you need maximum volume from a single query.
    Returns aggregated results from up to max_pages pages in one call.

    Unlike apollo_company_search (single page), this tool internally loops through
    pages and returns all results combined. Use this for Stage 1 broad discovery queries.
    Use apollo_company_search for Stage 2/4 targeted single-page lookups.

    Args:
        query: Search query describing the type of company (e.g., "medical device manufacturer")
        industries: Optional list of industry terms as keyword tags
        locations: List of locations (cities, states, countries)
        min_employees: Minimum number of employees
        max_employees: Maximum number of employees
        revenue_range: Revenue filter ranges as strings.
            Valid values: "0,1000000", "1000000,10000000", "10000000,50000000",
            "50000000,100000000", "100000000,500000000", "500000000,1000000000",
            "1000000000,"
        max_pages: Maximum number of pages to fetch (default 5, max 10). Each page = per_page results.
            Use max_pages=5 for broad queries, max_pages=10 for high-value primary queries.
        per_page: Results per page (max 100, default 25)

    Returns:
        dict with 'organizations' list (all pages combined), 'pagination_summary',
        and 'total_available' from Apollo
    """
    settings = get_settings()
    url = f"{settings.APOLLO_BASE_URL}/mixed_companies/search"
    headers = {
        "X-Api-Key": settings.APOLLO_API_KEY,
        "Content-Type": "application/json",
    }

    max_pages = min(max_pages, 10)
    per_page = min(per_page, 100)

    keyword_tags = []
    if query:
        keyword_tags.append(query)
    if industries:
        keyword_tags.extend(industries)

    all_organizations = []
    pages_fetched = 0
    total_available = 0
    exhausted = False
    rate_limited = False

    for page_num in range(1, max_pages + 1):
        payload = {
            "q_organization_keyword_tags": keyword_tags if keyword_tags else None,
            "organization_locations": locations,
            "organization_num_employees_ranges": (
                [f"{min_employees or ''},{max_employees or ''}"]
                if min_employees or max_employees
                else None
            ),
            "organization_revenue_ranges": revenue_range,
            "page": page_num,
            "per_page": per_page,
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        try:
            response = httpx_post_with_retry(url, json=payload, headers=headers, timeout=30, max_retries=1)
            if response.status_code in RATE_LIMIT_CODES:
                logger.warning(f"Apollo rate-limited on page {page_num}. Returning partial results.")
                rate_limited = True
                break
            response.raise_for_status()
            data = response.json()

            orgs = data.get("organizations", [])
            all_organizations.extend(orgs)
            pages_fetched = page_num

            pagination = data.get("pagination", {})
            total_available = pagination.get("total_entries", total_available)

            if not orgs or len(orgs) < per_page:
                exhausted = True
                break

        except httpx.HTTPStatusError as e:
            if e.response.status_code in RATE_LIMIT_CODES:
                logger.warning(f"Apollo rate-limited on page {page_num}. Returning partial results.")
                rate_limited = True
                break
            logger.warning(f"Apollo paginated search failed on page {page_num}: {e}")
            break
        except Exception as e:
            logger.warning(f"Apollo paginated search error on page {page_num}: {e}")
            break

        # Rate-limit courtesy delay between pages
        if page_num < max_pages:
            time.sleep(0.5)

    logger.info(
        f"Apollo paginated: {pages_fetched} pages, {len(all_organizations)} orgs "
        f"(total available: {total_available})"
    )

    # Trim org records to essential fields to prevent context window overflow
    all_organizations = [_trim_org(o) for o in all_organizations]

    result = {
        "organizations": all_organizations,
        "pagination_summary": {
            "pages_fetched": pages_fetched,
            "total_results_returned": len(all_organizations),
            "total_available": total_available,
            "exhausted": exhausted,
            "rate_limited": rate_limited,
        },
    }

    if rate_limited:
        result["warning"] = (
            "Apollo rate limit hit. Partial results returned. "
            "Switch to exa_search or tavily_search for remaining queries."
        )

    return result


@tool
def apollo_people_search(
    company_name: str = None,
    company_domain: str = None,
    titles: list[str] = None,
    locations: list[str] = None,
    seniorities: list[str] = None,
    departments: list[str] = None,
    email_status: list[str] = None,
    page: int = 1,
    per_page: int = 25,
) -> dict:
    """
    Search for people/contacts at specific companies using Apollo.io.
    BEST FOR: Finding decision-makers by title at known companies.
    USE IN STAGE: Contact Discovery (Stage 2)

    Args:
        company_name: Name of the company to search within
        company_domain: Domain of the company (e.g., "acme.com")
        titles: List of job titles to filter by (e.g., ["CTO", "VP Engineering"])
        locations: List of locations to filter
        seniorities: Filter by seniority level. Valid values:
            "c_suite", "vp", "director", "manager", "senior", "entry", "owner", "founder", "partner"
        departments: Filter by department. Valid values:
            "engineering", "executive", "finance", "human_resources", "information_technology",
            "marketing", "operations", "sales", "support", "legal"
        email_status: Filter by email verification status.
            Use ["verified"] to only get contacts with verified emails (recommended).
            Valid values: "verified", "guessed", "unavailable"
        page: Page number for pagination
        per_page: Results per page (max 25)

    Returns:
        dict with 'people' list containing name, title, email, linkedin, phone
    """
    settings = get_settings()
    url = f"{settings.APOLLO_BASE_URL}/mixed_people/search"
    headers = {
        "X-Api-Key": settings.APOLLO_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "q_organization_name": company_name,
        "organization_domains": [company_domain] if company_domain else None,
        "person_titles": titles,
        "person_locations": locations,
        "person_seniorities": seniorities,
        "person_departments": departments,
        "contact_email_status": email_status,
        "page": page,
        "per_page": min(per_page, 25),
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True, "people": []}
        if e.response.status_code == 422:
            body = ""
            try:
                body = e.response.text[:300]
            except Exception:
                pass
            return {
                "error": (
                    f"Apollo rejected the request (422). Try simpler parameters. "
                    f"Details: {body}"
                ),
                "people": [],
            }
        return {"error": str(e), "people": []}
    except Exception as e:
        return {"error": str(e), "people": []}
