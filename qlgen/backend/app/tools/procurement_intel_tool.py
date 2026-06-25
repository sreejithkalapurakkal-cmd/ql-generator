"""Procurement intelligence tool.

Scans for RFP/RFI activity, government procurement portals,
and vendor registration signals for target companies.
"""
import logging
import re

from strands import tool

logger = logging.getLogger(__name__)

# Procurement signal type keywords
PROCUREMENT_TYPE_KEYWORDS = {
    "rfp": [
        "request for proposal", "rfp", "request for proposals",
        "solicitation", "call for proposals",
    ],
    "rfi": [
        "request for information", "rfi", "request for interest",
        "market survey", "sources sought",
    ],
    "bid": [
        "invitation to bid", "itb", "sealed bid", "competitive bid",
        "public bid", "bid opportunity", "tender", "invitation to tender",
    ],
    "vendor_registration": [
        "vendor registration", "supplier registration", "vendor qualification",
        "approved vendor", "vendor portal", "supplier portal",
        "prequalification", "pre-qualification",
    ],
    "contract_award": [
        "contract award", "awarded contract", "contract winner",
        "selected vendor", "awarded to", "contract value",
        "notice of award", "sole source",
    ],
}

# Keywords suggesting monetary value
VALUE_PATTERNS = [
    r"\$[\d,.]+\s*(?:million|M|billion|B|thousand|K)?",
    r"(?:valued at|worth|estimated at|budget of)\s*\$[\d,.]+",
    r"(?:USD|EUR|GBP)\s*[\d,.]+",
]


@tool
def scan_procurement_activity(
    company_name: str,
    domain: str,
    keywords: list[str] = None,
) -> dict:
    """Scan for procurement and RFP activity related to a company.

    Searches for RFPs, RFIs, bids, vendor registrations, and contract awards
    involving the target company.

    Args:
        company_name: Name of the company to investigate
        domain: Company domain (e.g., 'acme.com')
        keywords: Optional additional keywords to refine the search
            (e.g., ['cloud', 'cybersecurity'])

    Returns:
        dict with company, procurement_signals, signal_strength, total_found
    """
    from app.tools.duckduckgo_tool import duckduckgo_search

    result = {
        "company": company_name,
        "procurement_signals": [],
        "signal_strength": 0.0,
        "total_found": 0,
    }

    # Build search queries
    queries = [
        f'"{company_name}" RFP OR RFI OR procurement OR bid',
        f'"{company_name}" vendor selection OR contract award',
    ]

    # Add keyword-specific queries
    if keywords:
        for keyword in keywords[:3]:  # Limit to avoid too many searches
            queries.append(f'"{company_name}" {keyword} procurement OR RFP')

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
                f"Procurement scan failed for '{company_name}' "
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

        # Verify the article relates to the target company
        company_lower = company_name.lower()
        domain_base = domain.split(".")[0].lower() if domain else ""
        if company_lower not in text_lower and domain_base not in text_lower:
            continue

        # Deduplicate by normalized title
        title_key = title.strip().lower()[:80]
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        # Detect procurement signal type
        signal_type = _detect_procurement_type(text_lower)
        if not signal_type:
            continue

        # Try to extract estimated value
        estimated_value = _extract_value(text)

        # Try to extract a date
        date_ref = _extract_date(text)

        # Build a concise description from the body
        description = (body or title)[:300].strip()

        signal = {
            "type": signal_type,
            "title": title[:200].strip(),
            "description": description,
            "date": date_ref,
            "source_url": href,
            "estimated_value": estimated_value,
        }

        result["procurement_signals"].append(signal)

    result["total_found"] = len(result["procurement_signals"])
    result["signal_strength"] = _calculate_signal_strength(result["procurement_signals"])

    return result


def _detect_procurement_type(text_lower: str) -> str | None:
    """Identify the procurement signal type from text content."""
    scores: dict[str, int] = {}
    for ptype, keywords in PROCUREMENT_TYPE_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in text_lower)
        if count > 0:
            scores[ptype] = count

    if scores:
        return max(scores, key=scores.get)
    return None


def _extract_value(text: str) -> str | None:
    """Extract estimated monetary value from text."""
    for pattern in VALUE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return None


def _extract_date(text: str) -> str | None:
    """Extract a date reference from text."""
    patterns = [
        r"(\w+\s+\d{1,2},?\s+\d{4})",        # January 15, 2026
        r"(\d{1,2}/\d{1,2}/\d{4})",            # 01/15/2026
        r"(\d{4}-\d{2}-\d{2})",                # 2026-01-15
        r"(Q[1-4]\s+\d{4})",                   # Q1 2026
        r"(?:deadline|due):\s*(\w+\s+\d{1,2},?\s+\d{4})",  # deadline: Jan 15, 2026
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1) if match.lastindex else match.group(0)
    return None


def _calculate_signal_strength(signals: list[dict]) -> float:
    """Calculate signal strength (0-100) based on procurement signals found."""
    if not signals:
        return 0.0

    score = 0.0

    # Weight by signal type
    type_weights = {
        "rfp": 25.0,
        "rfi": 15.0,
        "bid": 20.0,
        "vendor_registration": 10.0,
        "contract_award": 30.0,
    }

    for signal in signals:
        signal_type = signal.get("type", "")
        score += type_weights.get(signal_type, 5.0)

        # Bonus if monetary value was detected
        if signal.get("estimated_value"):
            score += 10.0

    return min(100.0, round(score, 1))
