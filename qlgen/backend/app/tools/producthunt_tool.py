"""ProductHunt API tool for startup/tech company discovery.

Uses the ProductHunt API to discover recently-launched products and their
maker companies. Returns product details, maker profiles (often with
LinkedIn/email), and launch metrics.

Requires PRODUCTHUNT_TOKEN env var (free developer token from
https://www.producthunt.com/v2/oauth/applications).
"""

import logging
import os

from strands import tool

from app.tools.retry_utils import httpx_post_with_retry, httpx_get_with_retry

logger = logging.getLogger(__name__)

PRODUCTHUNT_API = "https://api.producthunt.com/v2/api/graphql"


@tool
def search_producthunt(
    topic: str,
    max_results: int = 50,
) -> dict:
    """
    Search ProductHunt for recently launched products by topic/keyword.
    Requires PRODUCTHUNT_TOKEN env var (free developer token).

    Useful for discovering startups and tech companies through their product
    launches. Maker profiles often include LinkedIn URLs and emails.

    USE IN STAGES: Stage 1 (Discovery) for tech/SaaS/startup companies,
    Stage 4 (Contacts) for maker profiles.

    Args:
        topic: Topic or keyword to search (e.g. "medical device", "devtools",
               "AI", "cybersecurity", "fintech")
        max_results: Maximum products to return (max 50)

    Returns:
        dict with 'products' list (including maker info), 'companies' list
        (unique companies extracted), and 'total_found'
    """
    token = os.environ.get("PRODUCTHUNT_TOKEN")

    if not token:
        return {
            "error": "PRODUCTHUNT_TOKEN env var required. "
                     "Get free at https://www.producthunt.com/v2/oauth/applications",
            "products": [],
            "companies": [],
            "configured": False,
        }

    query = """
    query SearchPosts($query: String!, $first: Int!) {
        posts(order: RANKING, search: $query, first: $first) {
            edges {
                node {
                    id
                    name
                    tagline
                    description
                    url
                    website
                    votesCount
                    commentsCount
                    createdAt
                    topics {
                        edges {
                            node {
                                name
                            }
                        }
                    }
                    makers {
                        id
                        name
                        headline
                        username
                        websiteUrl
                        twitterUsername
                    }
                }
            }
        }
    }
    """

    try:
        response = httpx_post_with_retry(
            PRODUCTHUNT_API,
            json={
                "query": query,
                "variables": {
                    "query": topic,
                    "first": min(max_results, 50),
                },
            },
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=20,
        )

        if response.status_code == 401:
            return {
                "error": "ProductHunt token invalid or expired",
                "products": [],
                "companies": [],
            }

        if response.status_code != 200:
            return {
                "error": f"ProductHunt API returned HTTP {response.status_code}",
                "products": [],
                "companies": [],
            }

        data = response.json()
        edges = (data.get("data", {}).get("posts", {}).get("edges", []))

        products = []
        companies: dict[str, dict] = {}

        for edge in edges:
            node = edge.get("node", {})

            topics = [
                t["node"]["name"]
                for t in node.get("topics", {}).get("edges", [])
            ]

            makers = []
            for maker in node.get("makers", []):
                makers.append({
                    "name": maker.get("name", ""),
                    "headline": maker.get("headline", ""),
                    "username": maker.get("username", ""),
                    "website": maker.get("websiteUrl", ""),
                    "twitter": maker.get("twitterUsername", ""),
                    "producthunt_url": f"https://www.producthunt.com/@{maker.get('username', '')}",
                })

            product = {
                "name": node.get("name", ""),
                "tagline": node.get("tagline", ""),
                "description": (node.get("description") or "")[:300],
                "website": node.get("website", ""),
                "producthunt_url": node.get("url", ""),
                "votes": node.get("votesCount", 0),
                "comments": node.get("commentsCount", 0),
                "created_at": node.get("createdAt", ""),
                "topics": topics,
                "makers": makers,
                "source": "producthunt",
            }
            products.append(product)

            # Extract company from website domain
            website = node.get("website", "")
            if website:
                domain = website.lower().replace("https://", "").replace("http://", "").rstrip("/")
                if domain and domain not in companies:
                    companies[domain] = {
                        "name": node.get("name", ""),
                        "website": website,
                        "description": node.get("tagline", ""),
                        "topics": topics,
                        "product_count": 0,
                        "total_votes": 0,
                        "makers": [],
                        "source": "producthunt",
                    }
                if domain in companies:
                    companies[domain]["product_count"] += 1
                    companies[domain]["total_votes"] += node.get("votesCount", 0)
                    for maker in makers:
                        if maker not in companies[domain]["makers"]:
                            companies[domain]["makers"].append(maker)

        companies_list = sorted(
            companies.values(),
            key=lambda c: c["total_votes"],
            reverse=True,
        )

        logger.info(
            f"ProductHunt: {len(products)} products, {len(companies_list)} companies "
            f"for topic='{topic}'"
        )

        return {
            "products": products,
            "companies": companies_list,
            "total_found": len(products),
        }

    except Exception as e:
        logger.error(f"ProductHunt search failed: {e}")
        return {"error": str(e), "products": [], "companies": []}
