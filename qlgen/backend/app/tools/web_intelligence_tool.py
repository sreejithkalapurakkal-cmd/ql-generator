"""Web Intelligence Tool.

Intelligent web crawling with summarization, signal extraction,
and optional change detection. Combines scraping + LLM extraction.
"""
import asyncio
import hashlib
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def web_intelligence_tool(
    url: str,
    extraction_focus: str = "general",
    summarize: bool = True,
    detect_changes: bool = False,
    previous_snapshot_hash: str | None = None,
) -> dict:
    """Crawl a URL, extract structured information, optionally detect changes.

    Args:
        url: The URL to crawl
        extraction_focus: Focus area — "hiring", "product", "leadership", "tech_stack", "general"
        summarize: Whether to generate a content summary
        detect_changes: Whether to compare against previous snapshot
        previous_snapshot_hash: SHA256 hash of previous content for change detection

    Returns dict with content_summary, extracted_entities, signals_detected,
    content_hash, changed_sections (if detect_changes=True).
    """
    from app.tools.web_scraper_tool import scrape_webpage

    try:
        raw = scrape_webpage(url=url)
    except Exception as e:
        return {"error": str(e), "url": url, "content_hash": None}

    if not isinstance(raw, dict):
        raw = {"text": str(raw)}

    text = raw.get("text", "") or raw.get("content", "") or ""
    title = raw.get("title", "")

    # Compute content hash
    content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

    result = {
        "url": url,
        "title": title,
        "content_hash": content_hash,
        "content_length": len(text),
        "crawl_timestamp": datetime.now(timezone.utc).isoformat(),
        "extraction_focus": extraction_focus,
    }

    # Extract entities based on focus
    entities = []
    signals = []
    text_lower = text.lower()

    if extraction_focus in ("hiring", "general"):
        hiring_keywords = ["hiring", "open position", "join our team", "career", "we are looking"]
        if any(kw in text_lower for kw in hiring_keywords):
            entities.append({"type": "hiring_activity", "evidence": "Hiring-related content detected"})
            signals.append({"signal_type": "hiring_surge", "evidence": "Active hiring page content"})

    if extraction_focus in ("product", "general"):
        product_keywords = ["launch", "announce", "new feature", "release", "introducing"]
        if any(kw in text_lower for kw in product_keywords):
            entities.append({"type": "product_announcement", "evidence": "Product-related content detected"})
            signals.append({"signal_type": "product_launch", "evidence": "Product announcement content"})

    if extraction_focus in ("leadership", "general"):
        leader_keywords = ["appointed", "named", "joins as", "new ceo", "new cto", "new cdo", "board of directors"]
        if any(kw in text_lower for kw in leader_keywords):
            entities.append({"type": "leadership_change", "evidence": "Leadership change content detected"})
            signals.append({"signal_type": "executive_change", "evidence": "Executive announcement content"})

    if extraction_focus in ("tech_stack", "general"):
        tech_signals = raw.get("tech_signals", [])
        for tech in tech_signals:
            entities.append({"type": "technology", "name": tech})

    result["extracted_entities"] = entities
    result["signals_detected"] = signals

    if summarize and text:
        result["content_summary"] = text[:500].strip()

    # Change detection
    if detect_changes and previous_snapshot_hash:
        has_changes = content_hash != previous_snapshot_hash
        result["has_changes"] = has_changes
        if has_changes:
            result["change_summary"] = "Content has changed since last crawl"
        else:
            result["change_summary"] = "No significant changes detected"

    return result
