"""Press release RSS feed tool for company/signal discovery.

Parses free RSS feeds from major press release distributors:
- GlobeNewswire
- PR Newswire
- BusinessWire

Press releases contain funding announcements (budget signal), executive
appointments (contacts), product launches (urgency signal), and company
names (discovery). Completely free, no API key required.
"""

import logging
import re
from datetime import datetime, timedelta

from strands import tool

from app.tools.retry_utils import httpx_get_with_retry

logger = logging.getLogger(__name__)

# RSS feed URLs for major press release services
RSS_FEEDS = {
    "globenewswire": "https://www.globenewswire.com/RssFeed/industry/{category}/feedTitle/GlobeNewswire+-+{category}",
    "prnewswire": "https://www.prnewswire.com/rss/industry/{category}+news.rss",
}

# Industry category mappings for feed URLs
INDUSTRY_CATEGORIES = {
    "technology": {
        "globenewswire": "Technology",
        "prnewswire": "technology",
    },
    "healthcare": {
        "globenewswire": "Health",
        "prnewswire": "health-care-hospitals",
    },
    "medical_device": {
        "globenewswire": "Medical+Devices",
        "prnewswire": "medical-devices",
    },
    "pharmaceutical": {
        "globenewswire": "Pharmaceuticals",
        "prnewswire": "pharmaceuticals",
    },
    "financial": {
        "globenewswire": "Banking+%26+Financial+Services",
        "prnewswire": "financial-services",
    },
    "manufacturing": {
        "globenewswire": "Manufacturing",
        "prnewswire": "manufacturing-industry",
    },
    "energy": {
        "globenewswire": "Energy",
        "prnewswire": "energy-mining-utilities",
    },
    "automotive": {
        "globenewswire": "Automotive",
        "prnewswire": "automotive-transportation",
    },
}


def _parse_simple_xml(text: str) -> list[dict]:
    """Extract items from RSS XML without requiring lxml/feedparser.

    Simple regex-based parsing to avoid extra dependencies.
    """
    items = []
    item_pattern = re.compile(r"<item>(.*?)</item>", re.DOTALL)
    title_pattern = re.compile(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", re.DOTALL)
    link_pattern = re.compile(r"<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>", re.DOTALL)
    desc_pattern = re.compile(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", re.DOTALL)
    date_pattern = re.compile(r"<pubDate>(.*?)</pubDate>", re.DOTALL)

    for match in item_pattern.finditer(text):
        item_xml = match.group(1)

        title_match = title_pattern.search(item_xml)
        link_match = link_pattern.search(item_xml)
        desc_match = desc_pattern.search(item_xml)
        date_match = date_pattern.search(item_xml)

        items.append({
            "title": title_match.group(1).strip() if title_match else "",
            "link": link_match.group(1).strip() if link_match else "",
            "description": desc_match.group(1).strip()[:500] if desc_match else "",
            "pub_date": date_match.group(1).strip() if date_match else "",
        })

    return items


def _extract_signals(title: str, description: str) -> list[str]:
    """Extract business signals from press release title and description."""
    text = f"{title} {description}".lower()
    signals = []

    funding_keywords = ["funding", "raises", "raised", "series a", "series b",
                        "series c", "investment", "venture", "capital"]
    if any(kw in text for kw in funding_keywords):
        signals.append("funding")

    exec_keywords = ["appoints", "appointed", "names", "named", "hires",
                     "hired", "ceo", "cto", "cfo", "vp", "president"]
    if any(kw in text for kw in exec_keywords):
        signals.append("executive_appointment")

    product_keywords = ["launches", "launched", "announces", "announced",
                        "introduces", "introduced", "unveils", "released"]
    if any(kw in text for kw in product_keywords):
        signals.append("product_launch")

    partnership_keywords = ["partnership", "partners with", "collaboration",
                            "agreement", "alliance", "joint venture"]
    if any(kw in text for kw in partnership_keywords):
        signals.append("partnership")

    acquisition_keywords = ["acquires", "acquired", "acquisition", "merger",
                            "merges", "takeover"]
    if any(kw in text for kw in acquisition_keywords):
        signals.append("acquisition")

    expansion_keywords = ["expands", "expansion", "opens", "new office",
                          "new facility", "enters", "market entry"]
    if any(kw in text for kw in expansion_keywords):
        signals.append("expansion")

    return signals


def _extract_company_from_title(title: str) -> str:
    """Try to extract the company name from a press release title.

    Press releases typically start with the company name, e.g.:
    "Acme Corp Announces New Product" -> "Acme Corp"
    """
    # Common patterns: "Company Name Announces...", "Company Name, Inc. Reports..."
    patterns = [
        r"^(.+?)\s+(?:Announces|Reports|Launches|Unveils|Introduces|Appoints|Names|Raises|Expands|Acquires|Partners|Enters|Opens|Signs|Closes|Receives|Achieves|Completes|Delivers|Secures|Wins)",
        r"^(.+?)(?:,\s*(?:Inc|LLC|Ltd|Corp|AG|GmbH|SA|PLC)\.?)\s+",
    ]
    for pattern in patterns:
        match = re.match(pattern, title, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if 2 < len(name) < 80:
                return name
    return ""


@tool
def search_press_releases(
    industry_keywords: list[str],
    signal_filter: list[str] | None = None,
    max_results: int = 50,
) -> dict:
    """
    Search recent press releases from major distributors (GlobeNewswire, PR Newswire)
    by industry category. FREE, no API key required.

    Press releases are strong signals: funding (budget), executive appointments
    (contacts), product launches (urgency), partnerships (growth).

    USE IN STAGES: Stage 1 (Discovery) for recently-active companies,
    Stage 3 (Signals) for funding/growth/expansion evidence.

    Args:
        industry_keywords: Industry terms to match against feed categories
            (e.g. ["medical device", "healthcare"], ["fintech", "financial"])
        signal_filter: Optional list of signal types to filter by
            (e.g. ["funding", "executive_appointment", "product_launch",
                    "partnership", "acquisition", "expansion"])
        max_results: Maximum press releases to return

    Returns:
        dict with 'press_releases' list (with signals and extracted company names),
        'companies_mentioned', and 'signal_summary'
    """
    # Match industry keywords to feed categories
    matched_categories = set()
    for kw in industry_keywords:
        kw_lower = kw.lower()
        for cat_key in INDUSTRY_CATEGORIES:
            if cat_key in kw_lower or kw_lower in cat_key:
                matched_categories.add(cat_key)

    # Default to technology if no category matched
    if not matched_categories:
        matched_categories.add("technology")

    all_items = []
    feeds_checked = 0

    for category in matched_categories:
        category_feeds = INDUSTRY_CATEGORIES.get(category, {})

        for source, feed_category in category_feeds.items():
            feed_template = RSS_FEEDS.get(source)
            if not feed_template:
                continue

            feed_url = feed_template.format(category=feed_category)
            feeds_checked += 1

            try:
                response = httpx_get_with_retry(
                    feed_url,
                    headers={
                        "User-Agent": "qlGen/1.0 (Lead Generation Research Tool)",
                        "Accept": "application/rss+xml, application/xml, text/xml",
                    },
                    timeout=15,
                )
                if response.status_code != 200:
                    continue

                items = _parse_simple_xml(response.text)
                for item in items:
                    item["source"] = source
                    item["category"] = category
                all_items.extend(items)

            except Exception as e:
                logger.debug(f"Failed to fetch {source}/{category} feed: {e}")
                continue

    # Enrich with signals and company names
    results = []
    companies_mentioned = {}
    signal_counts = {}

    for item in all_items:
        signals = _extract_signals(item["title"], item["description"])
        company_name = _extract_company_from_title(item["title"])

        # Apply signal filter if specified
        if signal_filter:
            if not any(s in signal_filter for s in signals):
                continue

        pr = {
            "title": item["title"],
            "link": item["link"],
            "pub_date": item["pub_date"],
            "description": item["description"],
            "source": item["source"],
            "category": item["category"],
            "signals": signals,
            "company_name": company_name,
        }
        results.append(pr)

        # Track companies
        if company_name:
            if company_name not in companies_mentioned:
                companies_mentioned[company_name] = {
                    "name": company_name,
                    "mention_count": 0,
                    "signals": set(),
                    "source": "press_releases",
                }
            companies_mentioned[company_name]["mention_count"] += 1
            companies_mentioned[company_name]["signals"].update(signals)

        for s in signals:
            signal_counts[s] = signal_counts.get(s, 0) + 1

    # Limit results
    results = results[:max_results]

    # Convert sets to lists for JSON serialization
    companies_list = []
    for comp in companies_mentioned.values():
        comp["signals"] = sorted(comp["signals"])
        companies_list.append(comp)
    companies_list.sort(key=lambda c: c["mention_count"], reverse=True)

    logger.info(
        f"Press releases: {len(results)} items from {feeds_checked} feeds, "
        f"{len(companies_list)} unique companies"
    )

    return {
        "press_releases": results,
        "companies_mentioned": companies_list[:50],
        "signal_summary": signal_counts,
        "feeds_checked": feeds_checked,
        "categories_matched": sorted(matched_categories),
    }
