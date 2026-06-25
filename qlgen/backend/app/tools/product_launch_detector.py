"""Product launch detection tool.

Detects product/feature announcements, launches, and major updates
at target companies using news and press sources.
"""
import logging
import re

from strands import tool

logger = logging.getLogger(__name__)

# Launch type keyword patterns
LAUNCH_TYPE_KEYWORDS = {
    "new_product": [
        "launches new", "introduces new", "unveils new", "announces new product",
        "debuts", "brand new", "first-ever", "all-new", "new offering",
        "new solution", "new service", "goes live",
    ],
    "major_update": [
        "major update", "version 2", "version 3", "v2", "v3", "v4",
        "next generation", "next-gen", "redesigned", "rebuilt",
        "overhaul", "2.0", "3.0", "major release", "major upgrade",
    ],
    "feature": [
        "new feature", "adds feature", "feature launch", "now supports",
        "rolls out", "introduces support", "adds support", "new capability",
        "enhanced", "new integration", "integrates with",
    ],
    "platform": [
        "new platform", "platform launch", "platform release",
        "marketplace launch", "api launch", "developer platform",
        "open platform", "self-service platform", "cloud platform",
    ],
}

# Keywords that indicate it is genuinely a product/launch article
PRODUCT_INDICATORS = [
    "product", "platform", "solution", "feature", "tool", "service",
    "software", "app", "application", "api", "sdk", "suite",
    "module", "dashboard", "portal", "engine", "framework",
]


@tool
def detect_product_launches(
    company_name: str,
    domain: str,
    time_window_days: int = 90,
) -> dict:
    """Detect product launches, feature announcements, and major updates at a company.

    Searches news and press sources for product-related announcements
    from the target company.

    Args:
        company_name: Name of the company to monitor
        domain: Company domain (e.g., 'acme.com')
        time_window_days: How far back to look in days (default 90)

    Returns:
        dict with company, launches, signal_strength, total_found
    """
    from app.tools.duckduckgo_tool import duckduckgo_search

    result = {
        "company": company_name,
        "launches": [],
        "signal_strength": 0.0,
        "total_found": 0,
    }

    # Search queries targeting product launches and announcements
    queries = [
        f'"{company_name}" launches OR announces OR unveils OR introduces new',
        f'"{company_name}" product launch OR platform release OR new feature',
    ]

    all_articles = []
    for query in queries:
        try:
            raw = duckduckgo_search(query=query, max_results=10)
            if isinstance(raw, list):
                articles = [
                    a for a in raw
                    if isinstance(a, dict)
                    and not a.get("rate_limited")
                    and not a.get("error")
                    and (a.get("title") or a.get("body"))
                ]
                all_articles.extend(articles)
        except Exception as e:
            logger.warning(
                f"Product launch detection failed for '{company_name}' "
                f"with query '{query[:60]}': {e}"
            )

    if not all_articles:
        return result

    seen_titles: set[str] = set()

    for article in all_articles:
        title = article.get("title", "") or ""
        body = article.get("body", "") or article.get("content", "") or ""
        href = article.get("href") or article.get("url")
        text = f"{title} {body}"
        text_lower = text.lower()

        # Verify the article is about this company
        company_lower = company_name.lower()
        domain_base = domain.split(".")[0].lower() if domain else ""
        if company_lower not in text_lower and domain_base not in text_lower:
            continue

        # Check that it actually relates to a product/launch
        has_product_indicator = any(ind in text_lower for ind in PRODUCT_INDICATORS)
        if not has_product_indicator:
            continue

        # Deduplicate by normalized title
        title_key = title.strip().lower()[:80]
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        # Detect launch type
        launch_type = _detect_launch_type(text_lower)
        if not launch_type:
            continue

        # Try to extract the product name
        product_name = _extract_product_name(text, company_name)

        # Extract date reference
        date_ref = _extract_date(text)

        # Build description
        description = (body or title)[:300].strip()

        launch_record = {
            "product_name": product_name or "Unknown Product",
            "launch_type": launch_type,
            "description": description,
            "date": date_ref,
            "source_url": href,
        }

        result["launches"].append(launch_record)

    result["total_found"] = len(result["launches"])
    result["signal_strength"] = _calculate_signal_strength(result["launches"])

    return result


def _detect_launch_type(text_lower: str) -> str | None:
    """Determine the type of product launch from text."""
    scores: dict[str, int] = {}
    for ltype, keywords in LAUNCH_TYPE_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in text_lower)
        if count > 0:
            scores[ltype] = count

    if scores:
        return max(scores, key=scores.get)
    return None


def _extract_product_name(text: str, company_name: str) -> str | None:
    """Attempt to extract the product/feature name from the article text.

    Uses several heuristics:
    1. Look for patterns like "launches ProductName" or "announces ProductName"
    2. Look for quoted product names
    3. Look for capitalized product-like words near launch keywords
    """
    # Pattern 1: "CompanyName launches/announces/unveils ProductName"
    launch_verbs = (
        r"(?:launches|launched|announces|announced|unveils|unveiled|"
        r"introduces|introduced|debuts|debuted|releases|released)"
    )
    pattern1 = (
        rf"(?:{re.escape(company_name)})\s+{launch_verbs}\s+"
        rf"([A-Z][A-Za-z0-9\s]+?)(?:\s*[,.]|\s+(?:a|an|the|for|to|with|that))"
    )
    match = re.search(pattern1, text, re.IGNORECASE)
    if match:
        name = match.group(1).strip()
        if len(name) > 2 and len(name) < 60:
            return name

    # Pattern 2: Quoted product names near launch keywords
    pattern2 = r'["\u201c]([^"\u201d]{3,50})["\u201d]'
    quoted = re.findall(pattern2, text)
    for q in quoted:
        q_lower = q.lower()
        # Filter out generic phrases
        if any(
            skip in q_lower
            for skip in ["said", "we are", "the company", "our", "this"]
        ):
            continue
        return q

    # Pattern 3: "new <ProductName>" or "<ProductName> platform/product/tool"
    pattern3 = r"\bnew\s+([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)?)\b"
    match = re.search(pattern3, text)
    if match:
        candidate = match.group(1).strip()
        if (
            candidate.lower() != company_name.lower()
            and candidate.lower() not in {"york", "jersey", "delhi", "zealand"}
            and len(candidate) > 2
        ):
            return candidate

    return None


def _extract_date(text: str) -> str | None:
    """Extract a date reference from the text."""
    patterns = [
        r"(\w+\s+\d{1,2},?\s+\d{4})",        # January 15, 2026
        r"(\d{1,2}/\d{1,2}/\d{4})",            # 01/15/2026
        r"(\d{4}-\d{2}-\d{2})",                # 2026-01-15
        r"(Q[1-4]\s+\d{4})",                   # Q1 2026
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def _calculate_signal_strength(launches: list[dict]) -> float:
    """Calculate signal strength (0-100) based on launches detected."""
    if not launches:
        return 0.0

    score = 0.0

    type_weights = {
        "new_product": 30.0,
        "platform": 25.0,
        "major_update": 20.0,
        "feature": 10.0,
    }

    for launch in launches:
        launch_type = launch.get("launch_type", "")
        score += type_weights.get(launch_type, 5.0)

    return min(100.0, round(score, 1))
