import logging
import time
import httpx
from strands import tool
from app.config import get_settings
from app.tools.retry_utils import httpx_post_with_retry, httpx_get_with_retry

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

# Fields to keep from organization enrichment responses.
_ORG_ENRICH_KEEP_FIELDS = {
    "name", "website_url", "industry", "estimated_num_employees",
    "annual_revenue", "annual_revenue_printed", "founded_year",
    "city", "state", "country", "short_description",
    "total_funding", "total_funding_printed", "latest_funding_round_date",
    "linkedin_url",
}


def _trim_enriched_org(org: dict) -> dict:
    """Trim an enriched organization record to essential fields."""
    trimmed = {k: org.get(k) for k in _ORG_ENRICH_KEEP_FIELDS}
    desc = trimmed.get("short_description") or ""
    trimmed["short_description"] = desc[:300]
    tech = org.get("technology_names") or []
    if tech:
        trimmed["technology_names"] = tech[:20]
    return {k: v for k, v in trimmed.items() if v is not None}


def _trim_person(person: dict) -> dict:
    """Trim a person enrichment record to essential contact fields."""
    trimmed = {
        "name": person.get("name"),
        "first_name": person.get("first_name"),
        "last_name": person.get("last_name"),
        "title": person.get("title"),
        "email": person.get("email"),
        "linkedin_url": person.get("linkedin_url"),
        "city": person.get("city"),
        "state": person.get("state"),
        "country": person.get("country"),
    }
    # Phone may come from different fields
    phone = (
        person.get("sanitized_phone")
        or person.get("phone_number")
        or person.get("first_phone")
    )
    if phone:
        trimmed["phone"] = phone
    # Organization info
    org = person.get("organization") or {}
    if org:
        trimmed["organization_name"] = org.get("name")
    # Employment history (last 3 entries)
    employment = person.get("employment_history") or []
    if employment:
        trimmed["employment_history"] = [
            {
                "organization_name": e.get("organization_name"),
                "title": e.get("title"),
                "start_date": e.get("start_date"),
                "end_date": e.get("end_date"),
            }
            for e in employment[:3]
        ]
    return {k: v for k, v in trimmed.items() if v is not None}


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


# ──────────────────────────────────────────────────────────────────
# Organization Enrichment
# ──────────────────────────────────────────────────────────────────

@tool
def apollo_org_enrich(
    domain: str = None,
    name: str = None,
) -> dict:
    """
    Get detailed firmographic data for a company using Apollo.io Organization Enrichment.
    BEST FOR: Verifying revenue, employee count, tech stack, and funding for a KNOWN company.
    USE IN STAGE: Firmographic Fit (Stage 2) — much more reliable than apollo_company_search
    for firmographic verification.

    Returns structured data: revenue, employee count, industry, tech stack,
    funding details, founding year, and more.

    Args:
        domain: Company domain (e.g., "acme.com") — preferred identifier, highest match rate
        name: Company name (fallback if domain unavailable)

    Returns:
        dict with organization profile including estimated_num_employees,
        annual_revenue, technology_names, total_funding, etc.
    """
    settings = get_settings()
    if not domain and not name:
        return {"error": "Provide at least domain or name.", "organization": {}}

    url = f"{settings.APOLLO_BASE_URL}/organizations/enrich"
    headers = {
        "X-Api-Key": settings.APOLLO_API_KEY,
        "Content-Type": "application/json",
    }
    params = {}
    if domain:
        params["domain"] = domain
    if name:
        params["organization_name"] = name

    try:
        response = httpx_get_with_retry(url, params=params, headers=headers, timeout=30, max_retries=1)
        response.raise_for_status()
        data = response.json()
        org = data.get("organization") or data
        return {"organization": _trim_enriched_org(org)}
    except httpx.HTTPStatusError as e:
        resp_body = ""
        try:
            resp_body = e.response.text[:500]
        except Exception:
            pass
        logger.warning(f"Apollo org enrich HTTP {e.response.status_code}: {resp_body}")

        if e.response.status_code in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True, "organization": {}}
        if e.response.status_code in (401, 403):
            return {"error": f"Apollo authentication error ({e.response.status_code}). Check API key.", "organization": {}}
        return {"error": f"Apollo org enrich error ({e.response.status_code}): {resp_body}", "organization": {}}
    except Exception as e:
        return {"error": str(e), "organization": {}}


@tool
def apollo_org_enrich_bulk(
    domains: list[str],
) -> dict:
    """
    Enrich up to 10 organizations at once with firmographic data using Apollo.io.
    BEST FOR: Batch firmographic verification in Stage 2 — much more efficient than
    individual calls. Pass company domains to get revenue, employees, tech stack, funding.

    Args:
        domains: List of company domains (max 10, e.g., ["acme.com", "stripe.com"])

    Returns:
        dict with 'organizations' list containing enriched profiles for each domain
    """
    settings = get_settings()
    if not domains:
        return {"error": "Provide at least one domain.", "organizations": []}

    domains = domains[:10]  # Apollo bulk limit
    url = f"{settings.APOLLO_BASE_URL}/organizations/bulk_enrich"
    headers = {
        "X-Api-Key": settings.APOLLO_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {"domains": domains}

    try:
        response = httpx_post_with_retry(url, json=payload, headers=headers, timeout=60, max_retries=1)
        response.raise_for_status()
        data = response.json()
        orgs = data.get("organizations") or []
        return {
            "organizations": [_trim_enriched_org(o) for o in orgs],
            "total_returned": len(orgs),
            "domains_requested": len(domains),
        }
    except httpx.HTTPStatusError as e:
        resp_body = ""
        try:
            resp_body = e.response.text[:500]
        except Exception:
            pass
        logger.warning(f"Apollo bulk org enrich HTTP {e.response.status_code}: {resp_body}")

        if e.response.status_code in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True, "organizations": []}
        if e.response.status_code in (401, 403):
            return {"error": f"Apollo authentication error ({e.response.status_code}).", "organizations": []}
        return {"error": f"Apollo bulk org enrich error ({e.response.status_code}): {resp_body}", "organizations": []}
    except Exception as e:
        return {"error": str(e), "organizations": []}


# ──────────────────────────────────────────────────────────────────
# People Enrichment
# ──────────────────────────────────────────────────────────────────

@tool
def apollo_people_enrich(
    first_name: str = None,
    last_name: str = None,
    name: str = None,
    email: str = None,
    linkedin_url: str = None,
    company_name: str = None,
    company_domain: str = None,
    reveal_personal_emails: bool = False,
    reveal_phone_number: bool = True,
) -> dict:
    """
    Enrich a person's profile with verified emails, phone numbers, and employment history.
    BEST FOR: Getting actual contact details (email, phone, LinkedIn) for a KNOWN person.
    USE IN STAGE: Contact Discovery (Stage 4) — call AFTER apollo_people_search finds contacts.

    IMPORTANT: apollo_people_search finds people by name/title but does NOT return emails
    or phone numbers. You MUST call this tool to get actual contact details.

    Provide at least one identifier combination:
    - linkedin_url (best match rate)
    - first_name + last_name + company_domain
    - email address

    Args:
        first_name: Person's first name
        last_name: Person's last name
        name: Full name (alternative to first_name + last_name)
        email: Known email address for matching
        linkedin_url: LinkedIn profile URL (highest match rate)
        company_name: Company name for disambiguation
        company_domain: Company domain for disambiguation (e.g., "acme.com")
        reveal_personal_emails: Request personal emails (uses additional credits)
        reveal_phone_number: Request phone numbers (uses additional credits, default True)

    Returns:
        dict with person profile including email, phone, linkedin_url,
        title, organization, employment_history
    """
    settings = get_settings()
    url = f"{settings.APOLLO_BASE_URL}/people/match"
    headers = {
        "X-Api-Key": settings.APOLLO_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {}
    if first_name:
        payload["first_name"] = first_name
    if last_name:
        payload["last_name"] = last_name
    if name:
        payload["name"] = name
    if email:
        payload["email"] = email
    if linkedin_url:
        payload["linkedin_url"] = linkedin_url
    if company_name:
        payload["organization_name"] = company_name
    if company_domain:
        payload["domain"] = company_domain
    if reveal_personal_emails:
        payload["reveal_personal_emails"] = True
    if reveal_phone_number:
        payload["reveal_phone_number"] = True

    if not any(k in payload for k in ("first_name", "name", "email", "linkedin_url")):
        return {"error": "Provide at least one identifier: name, email, or linkedin_url.", "person": {}}

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        person = data.get("person") or data
        if not person or person == data:
            return {"error": "No matching person found.", "person": {}}
        return {"person": _trim_person(person)}
    except httpx.HTTPStatusError as e:
        resp_body = ""
        try:
            resp_body = e.response.text[:500]
        except Exception:
            pass
        logger.warning(f"Apollo people enrich HTTP {e.response.status_code}: {resp_body}")

        if e.response.status_code in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True, "person": {}}
        if e.response.status_code == 422:
            return {"error": f"Apollo rejected request (422). Simplify identifiers. Details: {resp_body}", "person": {}}
        if e.response.status_code in (401, 403):
            return {"error": f"Apollo authentication error ({e.response.status_code}).", "person": {}}
        return {"error": f"Apollo people enrich error ({e.response.status_code}): {resp_body}", "person": {}}
    except Exception as e:
        return {"error": str(e), "person": {}}


@tool
def apollo_people_enrich_bulk(
    people: list[dict],
    reveal_phone_number: bool = True,
) -> dict:
    """
    Enrich up to 10 people at once with verified emails, phone numbers, and profiles.
    BEST FOR: Batch contact enrichment after apollo_people_search finds multiple contacts.
    USE IN STAGE: Contact Discovery (Stage 4) — PREFERRED over individual enrichment.

    Each person dict must contain at least one identifier:
    - {"first_name": "Jane", "last_name": "Doe", "organization_name": "Acme Inc"}
    - {"linkedin_url": "https://linkedin.com/in/janedoe"}
    - {"email": "jane@acme.com"}

    Args:
        people: List of person identifier dicts (max 10). Each must have identifying fields.
        reveal_phone_number: Request phone numbers for all people (uses credits per person)

    Returns:
        dict with 'matches' list containing enriched person profiles with email, phone, title
    """
    settings = get_settings()
    if not people:
        return {"error": "Provide at least one person.", "matches": []}

    people = people[:10]  # Apollo bulk limit
    url = f"{settings.APOLLO_BASE_URL}/people/bulk_match"
    headers = {
        "X-Api-Key": settings.APOLLO_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "details": people,
        "reveal_phone_number": reveal_phone_number,
    }

    try:
        response = httpx_post_with_retry(url, json=payload, headers=headers, timeout=60, max_retries=1)
        response.raise_for_status()
        data = response.json()
        matches = data.get("matches") or data.get("people") or []
        return {
            "matches": [_trim_person(m) for m in matches if m],
            "total_returned": len([m for m in matches if m]),
            "people_requested": len(people),
        }
    except httpx.HTTPStatusError as e:
        resp_body = ""
        try:
            resp_body = e.response.text[:500]
        except Exception:
            pass
        logger.warning(f"Apollo bulk people enrich HTTP {e.response.status_code}: {resp_body}")

        if e.response.status_code in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True, "matches": []}
        if e.response.status_code in (401, 403):
            return {"error": f"Apollo authentication error ({e.response.status_code}).", "matches": []}
        return {"error": f"Apollo bulk enrich error ({e.response.status_code}): {resp_body}", "matches": []}
    except Exception as e:
        return {"error": str(e), "matches": []}


# ──────────────────────────────────────────────────────────────────
# News Articles Search
# ──────────────────────────────────────────────────────────────────

@tool
def apollo_news_search(
    company_name: str = None,
    company_domain: str = None,
    max_results: int = 10,
) -> dict:
    """
    Search for news articles about a company using Apollo.io News Articles Search.
    BEST FOR: Finding company-specific news — funding rounds, partnerships, product launches,
    executive appointments. Works for PRIVATE companies not covered by SEC/SimFin.
    USE IN STAGE: Signal Research (Stage 3) — budget and urgency signals from news.

    Args:
        company_name: Name of the company to search news for
        company_domain: Company domain (e.g., "acme.com")
        max_results: Maximum number of articles to return (default 10)

    Returns:
        dict with 'articles' list containing title, url, published_date, source, snippet
    """
    settings = get_settings()
    if not company_name and not company_domain:
        return {"error": "Provide at least company_name or company_domain.", "articles": []}

    url = f"{settings.APOLLO_BASE_URL}/news_articles/search"
    headers = {
        "X-Api-Key": settings.APOLLO_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {}
    if company_name:
        payload["q_organization_name"] = company_name
    if company_domain:
        payload["organization_domains"] = [company_domain]
    payload["per_page"] = min(max_results, 25)
    payload["page"] = 1

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        articles = data.get("news_articles") or data.get("articles") or []
        trimmed = [
            {
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "published_date": a.get("published_date") or a.get("date", ""),
                "source": a.get("source") or a.get("publisher", ""),
                "snippet": (a.get("snippet") or a.get("description") or "")[:300],
            }
            for a in articles[:max_results]
        ]
        return {"articles": trimmed, "total_found": len(articles)}
    except httpx.HTTPStatusError as e:
        resp_body = ""
        try:
            resp_body = e.response.text[:500]
        except Exception:
            pass
        logger.warning(f"Apollo news search HTTP {e.response.status_code}: {resp_body}")

        if e.response.status_code in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True, "articles": []}
        if e.response.status_code in (401, 403):
            return {"error": f"Apollo authentication error ({e.response.status_code}).", "articles": []}
        return {"error": f"Apollo news search error ({e.response.status_code}): {resp_body}", "articles": []}
    except Exception as e:
        return {"error": str(e), "articles": []}
