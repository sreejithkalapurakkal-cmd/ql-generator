"""GitHub API tool for tech company discovery.

Uses the GitHub API to discover tech companies through open-source activity.
60 req/hr unauthenticated, 5000/hr with free token.

Returns organization profiles with: public member count (engineering team
size proxy), programming languages (tech stack), repository activity
(growth signal), and contributor emails.
"""

import logging
import os

from strands import tool

from app.tools.retry_utils import httpx_get_with_retry

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _github_headers() -> dict:
    """Build GitHub API headers, including auth token if available."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "qlGen/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


@tool
def search_github_organizations(
    query: str,
    language: str = "",
    location: str = "",
    max_results: int = 50,
) -> dict:
    """
    Search GitHub for organizations by industry keywords, programming language,
    and location. Useful for discovering tech companies through their open-source
    activity.

    FREE: 60 requests/hour without token, 5000/hour with free GITHUB_TOKEN.

    Returns organization profiles with: name, website, description, public repos,
    public member count (engineering team size proxy), and top languages (tech stack).

    USE IN STAGES: Stage 1 (Discovery) for tech companies, Stage 3 (Signals)
    for tech stack and growth signals.

    Args:
        query: Search keywords (e.g. "medical device software", "fintech API")
        language: Optional programming language filter (e.g. "python", "java")
        location: Optional location filter (e.g. "San Francisco", "Germany")
        max_results: Maximum number of organizations to return (max 100)

    Returns:
        dict with 'organizations' list, 'total_found', and 'rate_limit_remaining'
    """
    # Build search query
    search_parts = [query]
    if language:
        search_parts.append(f"language:{language}")
    if location:
        search_parts.append(f"location:{location}")
    search_query = " ".join(search_parts)

    try:
        # Search organizations
        response = httpx_get_with_retry(
            f"{GITHUB_API}/search/users",
            params={
                "q": f"{search_query} type:org",
                "per_page": min(max_results, 100),
                "sort": "followers",
                "order": "desc",
            },
            headers=_github_headers(),
            timeout=20,
        )

        if response.status_code == 403:
            return {
                "error": "RATE_LIMITED: GitHub API rate limit reached. Set GITHUB_TOKEN for 5000 req/hr.",
                "organizations": [],
                "rate_limited": True,
            }

        if response.status_code != 200:
            return {
                "error": f"GitHub API returned HTTP {response.status_code}",
                "organizations": [],
            }

        data = response.json()
        rate_remaining = response.headers.get("X-RateLimit-Remaining", "unknown")

        organizations = []
        for item in data.get("items", [])[:max_results]:
            login = item.get("login", "")

            # Fetch full org profile for more details
            org_details = _fetch_org_details(login)

            organizations.append({
                "name": org_details.get("name") or login,
                "github_login": login,
                "website": org_details.get("blog", ""),
                "description": org_details.get("description", ""),
                "location": org_details.get("location", ""),
                "public_repos": org_details.get("public_repos", 0),
                "public_members": org_details.get("public_members_count", item.get("followers", 0)),
                "email": org_details.get("email", ""),
                "twitter_username": org_details.get("twitter_username", ""),
                "top_languages": org_details.get("top_languages", []),
                "source": "github",
                "github_url": f"https://github.com/{login}",
            })

        logger.info(
            f"GitHub: found {len(organizations)} organizations for query='{query}', "
            f"rate_remaining={rate_remaining}"
        )

        return {
            "organizations": organizations,
            "total_found": data.get("total_count", 0),
            "returned": len(organizations),
            "rate_limit_remaining": rate_remaining,
        }

    except Exception as e:
        logger.error(f"GitHub search failed: {e}")
        return {"error": str(e), "organizations": []}


def _fetch_org_details(login: str) -> dict:
    """Fetch detailed organization profile."""
    try:
        response = httpx_get_with_retry(
            f"{GITHUB_API}/orgs/{login}",
            headers=_github_headers(),
            timeout=15,
        )
        if response.status_code != 200:
            return {}

        data = response.json()

        # Get top languages from their repos
        top_languages = _get_org_top_languages(login)

        # Get public members count
        members_count = 0
        members_response = httpx_get_with_retry(
            f"{GITHUB_API}/orgs/{login}/public_members",
            params={"per_page": 1},
            headers=_github_headers(),
            timeout=10,
        )
        if members_response.status_code == 200:
            # Parse from Link header for total count
            link_header = members_response.headers.get("Link", "")
            if "last" in link_header:
                import re
                match = re.search(r'page=(\d+)>; rel="last"', link_header)
                if match:
                    members_count = int(match.group(1))
            else:
                members_count = len(members_response.json())

        data["public_members_count"] = members_count
        data["top_languages"] = top_languages
        return data

    except Exception:
        return {}


def _get_org_top_languages(login: str) -> list[str]:
    """Get top programming languages used by an organization."""
    try:
        response = httpx_get_with_retry(
            f"{GITHUB_API}/orgs/{login}/repos",
            params={"per_page": 10, "sort": "updated", "direction": "desc"},
            headers=_github_headers(),
            timeout=15,
        )
        if response.status_code != 200:
            return []

        lang_counts: dict[str, int] = {}
        for repo in response.json():
            lang = repo.get("language")
            if lang:
                lang_counts[lang] = lang_counts.get(lang, 0) + 1

        # Sort by frequency
        sorted_langs = sorted(lang_counts.items(), key=lambda x: x[1], reverse=True)
        return [lang for lang, _ in sorted_langs[:5]]

    except Exception:
        return []
