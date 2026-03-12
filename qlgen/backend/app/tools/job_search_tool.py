"""Job posting search tool for contact discovery and org intelligence."""
import logging

from strands import tool

logger = logging.getLogger(__name__)


@tool
def search_job_postings(
    company_name: str,
    company_domain: str = "",
    role_keywords: list[str] = None,
) -> dict:
    """
    Search for a company's current job postings. Reveals: org structure, hiring velocity,
    tech stack from job descriptions, team size signals, and potential contacts (hiring managers).

    Uses DuckDuckGo to search across LinkedIn Jobs, Greenhouse, Lever, Workday, and company career pages.

    Args:
        company_name: Name of the company to search jobs for
        company_domain: Optional company domain (e.g. "acme.com") for career page search
        role_keywords: Optional list of role keywords to focus on (e.g. ["CTO", "VP Engineering"])

    Returns:
        dict with job_postings, hiring_signals, and org_insights
    """
    try:
        from ddgs import DDGS
        from ddgs.exceptions import RatelimitException
    except ImportError:
        return {"error": "DuckDuckGo library not available", "job_postings": []}

    role_keywords = role_keywords or []
    all_postings = []
    hiring_signals = []
    org_insights = []

    queries = [
        f'site:linkedin.com/jobs "{company_name}"',
        f'site:greenhouse.io "{company_name}"',
        f'site:lever.co "{company_name}"',
        f'"{company_name}" careers open positions',
    ]

    # Add role-specific queries
    for role in role_keywords[:3]:  # Limit to 3 roles to avoid rate limits
        queries.append(f'site:linkedin.com/jobs "{company_name}" {role}')

    # Add company domain career page search
    if company_domain:
        domain_clean = company_domain.replace("https://", "").replace("http://", "").rstrip("/")
        queries.append(f'site:{domain_clean} careers OR jobs OR "open positions"')

    try:
        with DDGS() as ddgs:
            for query in queries:
                try:
                    results = list(ddgs.text(query, max_results=5))
                    for r in results:
                        posting = {
                            "title": r.get("title", ""),
                            "url": r.get("href", ""),
                            "snippet": r.get("body", ""),
                            "source_query": query.split('"')[0].strip() if '"' in query else "general",
                        }

                        # Extract insights from job titles
                        title_lower = posting["title"].lower()
                        snippet_lower = posting["snippet"].lower()

                        # Detect hiring manager names in snippets
                        if "hiring manager" in snippet_lower or "reports to" in snippet_lower:
                            org_insights.append(f"Hiring manager signal in: {posting['title']}")

                        # Detect tech stack from descriptions
                        tech_keywords = [
                            "python", "java", "react", "aws", "azure", "gcp",
                            "kubernetes", "docker", "terraform", "salesforce",
                            "sap", "oracle", "snowflake", "databricks",
                        ]
                        found_tech = [t for t in tech_keywords if t in snippet_lower]
                        if found_tech:
                            org_insights.append(f"Tech stack from jobs: {', '.join(found_tech)}")

                        # Detect growth signals
                        growth_keywords = ["scaling", "growing", "expanding", "new team", "building"]
                        if any(g in snippet_lower for g in growth_keywords):
                            hiring_signals.append(f"Growth signal: {posting['title']}")

                        all_postings.append(posting)
                except RatelimitException:
                    hiring_signals.append("DuckDuckGo rate limited — partial results only")
                    break
                except Exception as e:
                    logger.debug(f"Job search query failed: {query} - {e}")
                    continue

    except RatelimitException:
        return {
            "error": "RATE_LIMITED: DuckDuckGo is blocking queries. Switch to other search tools.",
            "job_postings": [],
            "rate_limited": True,
        }
    except Exception as e:
        return {"error": str(e), "job_postings": []}

    # Deduplicate postings by URL
    seen_urls = set()
    unique_postings = []
    for p in all_postings:
        if p["url"] not in seen_urls:
            seen_urls.add(p["url"])
            unique_postings.append(p)

    return {
        "company_name": company_name,
        "total_postings_found": len(unique_postings),
        "job_postings": unique_postings[:20],  # Cap at 20
        "hiring_signals": list(set(hiring_signals)),
        "org_insights": list(set(org_insights)),
    }
