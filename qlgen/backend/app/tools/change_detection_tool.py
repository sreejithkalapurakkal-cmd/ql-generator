"""Change Detection Tool.

Compares current page state against stored hash, returns structured diff.
Used by the monitoring scheduler to detect meaningful changes on tracked pages.
"""
import hashlib
import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def change_detection_tool(
    url: str,
    previous_content_hash: str,
    change_types: list[str] | None = None,
) -> dict:
    """Compare current page state against stored hash, return structured diff.

    Args:
        url: URL to check
        previous_content_hash: SHA256 hash (first 16 chars) of previous content
        change_types: Types to check — ["content", "structure", "links", "meta"]

    Returns dict with has_changes, change_summary, significance_score, new_content_hash.
    """
    from app.tools.web_scraper_tool import scrape_webpage

    change_types = change_types or ["content"]

    try:
        raw = scrape_webpage(url=url)
    except Exception as e:
        return {
            "url": url,
            "error": str(e),
            "has_changes": False,
            "new_content_hash": None,
        }

    if not isinstance(raw, dict):
        raw = {"text": str(raw)}

    text = raw.get("text", "") or raw.get("content", "") or ""
    new_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

    has_changes = new_hash != previous_content_hash

    result = {
        "url": url,
        "has_changes": has_changes,
        "new_content_hash": new_hash,
        "previous_content_hash": previous_content_hash,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    if not has_changes:
        result["change_summary"] = "No changes detected"
        result["significance_score"] = 0.0
        return result

    # Analyze significance
    significance = 0.3  # Base score for any change

    # Check for meaningful content indicators
    meaningful_keywords = [
        "announce", "launch", "hire", "appoint", "partner", "acquire",
        "funding", "expand", "new office", "release", "migrate",
    ]
    text_lower = text.lower()
    keyword_matches = sum(1 for kw in meaningful_keywords if kw in text_lower)

    if keyword_matches >= 3:
        significance = 0.8
    elif keyword_matches >= 1:
        significance = 0.5

    # Check for structural changes (links, headers)
    if "structure" in change_types:
        links = re.findall(r'href="([^"]+)"', text)
        result["link_count"] = len(links)

    result["significance_score"] = round(significance, 2)
    result["change_summary"] = f"Content changed with {keyword_matches} meaningful keyword matches"
    result["keyword_matches"] = keyword_matches

    return result
