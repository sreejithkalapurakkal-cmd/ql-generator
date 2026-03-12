import httpx
from strands import tool

# YC community API — returns all ~5600+ YC companies in one request
YC_ALL_COMPANIES_URL = "https://yc-oss.github.io/api/companies/all.json"

_YC_CACHE: list[dict] | None = None


def _load_yc_companies() -> list[dict]:
    """Fetch and cache all YC companies."""
    global _YC_CACHE
    if _YC_CACHE is not None:
        return _YC_CACHE
    try:
        resp = httpx.get(YC_ALL_COMPANIES_URL, timeout=30)
        resp.raise_for_status()
        _YC_CACHE = resp.json()
        return _YC_CACHE
    except Exception as e:
        return []


@tool
def search_yc_companies(
    query: str = "",
    industries: list[str] = None,
    regions: list[str] = None,
    team_size_min: int = None,
    team_size_max: int = None,
    batch: str = "",
    status: str = "Active",
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """
    Search Y Combinator's public company directory. FREE, no API key required.
    BEST FOR: Finding startups and high-growth companies by industry, region, or team size.
    USE IN STAGE: Company Discovery (Stage 1) as a supplementary source.

    Args:
        query: Free-text search query matched against company name, one-liner, description
        industries: Filter by industries (e.g. ["B2B", "SaaS", "Healthcare"])
        regions: Filter by regions (e.g. ["United States", "Europe"])
        team_size_min: Minimum team size filter
        team_size_max: Maximum team size filter
        batch: YC batch filter (e.g. "W24", "S23")
        status: Company status filter ("Active", "Exited", "Inactive", "")
        page: Page number for pagination (1-based)
        per_page: Results per page (max 100)

    Returns:
        dict with 'companies' list, 'total_count', and 'page'
    """
    all_companies = _load_yc_companies()
    if not all_companies:
        return {"error": "Failed to load YC company data", "companies": [], "total_count": 0, "page": page}

    query_lower = query.strip().lower()
    industries_lower = [i.lower() for i in (industries or [])]
    regions_lower = [r.lower() for r in (regions or [])]
    batch_lower = batch.strip().lower()
    status_lower = status.strip().lower()

    filtered = []
    for c in all_companies:
        # Status filter
        if status_lower:
            company_status = (c.get("status") or "").lower()
            if company_status != status_lower:
                continue

        # Batch filter
        if batch_lower:
            company_batch = (c.get("batch") or "").lower()
            if batch_lower not in company_batch:
                continue

        # Team size filters
        team_size = c.get("team_size")
        if team_size is not None:
            if team_size_min is not None and team_size < team_size_min:
                continue
            if team_size_max is not None and team_size > team_size_max:
                continue

        # Industry filter — match against industries or tags fields
        if industries_lower:
            company_industries = [
                s.lower() for s in (c.get("industries") or c.get("tags") or [])
            ]
            company_text = (
                " ".join(company_industries)
                + " " + (c.get("one_liner") or "").lower()
                + " " + (c.get("long_description") or "").lower()[:200]
            )
            if not any(ind in company_text for ind in industries_lower):
                continue

        # Region filter
        if regions_lower:
            location = (c.get("all_locations") or "").lower()
            regions_field = [r.lower() for r in (c.get("regions") or [])]
            region_text = location + " " + " ".join(regions_field)
            if not any(reg in region_text for reg in regions_lower):
                continue

        # Query text search
        if query_lower:
            searchable = (
                (c.get("name") or "").lower()
                + " " + (c.get("one_liner") or "").lower()
                + " " + (c.get("long_description") or "").lower()[:300]
                + " " + " ".join(str(t).lower() for t in (c.get("tags") or []))
            )
            if query_lower not in searchable:
                continue

        filtered.append(c)

    total = len(filtered)
    per_page = min(per_page, 100)
    start = (page - 1) * per_page
    end = start + per_page
    page_results = filtered[start:end]

    result = []
    for c in page_results:
        result.append({
            "name": c.get("name", ""),
            "website": c.get("website", ""),
            "one_liner": c.get("one_liner", ""),
            "team_size": c.get("team_size"),
            "batch": c.get("batch", ""),
            "status": c.get("status", ""),
            "industries": c.get("industries") or c.get("tags") or [],
            "locations": c.get("all_locations", ""),
        })

    return {
        "companies": result,
        "total_count": total,
        "page": page,
    }
