import httpx
from strands import tool


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
        query: Free-text search query (company name, keyword, etc.)
        industries: Filter by industries (e.g. ["B2B", "SaaS", "Healthcare"])
        regions: Filter by regions (e.g. ["United States", "Europe"])
        team_size_min: Minimum team size filter
        team_size_max: Maximum team size filter
        batch: YC batch filter (e.g. "W24", "S23")
        status: Company status filter ("Active", "Exited", "Inactive")
        page: Page number for pagination
        per_page: Results per page (max 100)

    Returns:
        dict with 'companies' list, 'total_count', and 'page'
    """
    url = "https://api.ycombinator.com/v0.1/companies"
    params = {"page": page, "per_page": min(per_page, 100)}

    if query:
        params["q"] = query
    if batch:
        params["batch"] = batch
    if status:
        params["status"] = status

    # Build the JSON body for filters
    body = {}
    if industries:
        body["industries"] = industries
    if regions:
        body["regions"] = regions
    if team_size_min is not None or team_size_max is not None:
        team_size = {}
        if team_size_min is not None:
            team_size["min"] = team_size_min
        if team_size_max is not None:
            team_size["max"] = team_size_max
        body["team_size"] = team_size

    try:
        if body:
            response = httpx.post(url, params=params, json=body, timeout=30)
        else:
            response = httpx.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        companies = data.get("companies", [])
        result = []
        for c in companies:
            result.append({
                "name": c.get("name", ""),
                "website": c.get("website", c.get("url", "")),
                "one_liner": c.get("one_liner", ""),
                "team_size": c.get("team_size", None),
                "batch": c.get("batch", ""),
                "status": c.get("status", ""),
                "industries": c.get("industries", []),
            })

        return {
            "companies": result,
            "total_count": data.get("totalCount", data.get("total_count", len(result))),
            "page": page,
        }
    except Exception as e:
        return {"error": str(e), "companies": [], "total_count": 0, "page": page}
