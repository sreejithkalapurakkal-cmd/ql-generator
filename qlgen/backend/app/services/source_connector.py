"""Source Connector Framework.

ABC for source connectors + concrete implementations for
website, careers page, blog, and press release monitoring.
"""
import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.custom_signal_source import CustomSignalSource, SourceSnapshot
from app.events.event_bus import bus, Events

logger = logging.getLogger(__name__)


class CrawlResult:
    def __init__(self, content_hash: str, content_summary: str = "",
                 extracted_signals: list | None = None, error: str | None = None):
        self.content_hash = content_hash
        self.content_summary = content_summary
        self.extracted_signals = extracted_signals or []
        self.error = error


class SourceConnector(ABC):
    """Base class for all source connectors."""

    @abstractmethod
    async def crawl(self, source: CustomSignalSource) -> CrawlResult:
        """Crawl the source and return content hash + extracted data."""
        ...

    @abstractmethod
    async def extract_signals(self, content: str, company_name: str,
                               hypotheses: list[str] | None = None) -> list[dict]:
        """Extract signals from crawled content."""
        ...


class WebsiteConnector(SourceConnector):
    """Generic website crawling connector."""

    async def crawl(self, source: CustomSignalSource) -> CrawlResult:
        import asyncio
        from app.tools.web_intelligence_tool import web_intelligence_tool
        try:
            result = await asyncio.to_thread(
                web_intelligence_tool,
                url=source.url,
                extraction_focus="general",
                summarize=True,
                detect_changes=bool(source.last_content_hash),
                previous_snapshot_hash=source.last_content_hash,
            )
            return CrawlResult(
                content_hash=result.get("content_hash", ""),
                content_summary=result.get("content_summary", ""),
                extracted_signals=result.get("signals_detected", []),
                error=result.get("error"),
            )
        except Exception as e:
            return CrawlResult(content_hash="", error=str(e))

    async def extract_signals(self, content: str, company_name: str,
                               hypotheses: list[str] | None = None) -> list[dict]:
        from app.tools.intent_signal_extractor import intent_signal_extractor
        result = intent_signal_extractor(content, signal_hypotheses=hypotheses)
        return result.get("intent_signals", [])


class CareersPageConnector(SourceConnector):
    """Careers page monitoring — detects hiring patterns."""

    async def crawl(self, source: CustomSignalSource) -> CrawlResult:
        import asyncio
        from app.tools.web_intelligence_tool import web_intelligence_tool
        try:
            result = await asyncio.to_thread(
                web_intelligence_tool,
                url=source.url,
                extraction_focus="hiring",
                summarize=True,
                detect_changes=bool(source.last_content_hash),
                previous_snapshot_hash=source.last_content_hash,
            )
            return CrawlResult(
                content_hash=result.get("content_hash", ""),
                content_summary=result.get("content_summary", ""),
                extracted_signals=result.get("signals_detected", []),
            )
        except Exception as e:
            return CrawlResult(content_hash="", error=str(e))

    async def extract_signals(self, content: str, company_name: str,
                               hypotheses: list[str] | None = None) -> list[dict]:
        from app.tools.hiring_signal_detector import hiring_signal_detector
        result = hiring_signal_detector(company_name=company_name, domain="")
        signals = []
        if result.get("signal_strength", 0) > 30:
            signals.append({
                "signal_type": "hiring_surge",
                "title": f"{company_name} hiring activity detected",
                "strength": result["signal_strength"],
                "evidence": result,
            })
        return signals


class BlogConnector(SourceConnector):
    """Blog/news page monitoring."""

    async def crawl(self, source: CustomSignalSource) -> CrawlResult:
        import asyncio
        from app.tools.web_intelligence_tool import web_intelligence_tool
        try:
            result = await asyncio.to_thread(
                web_intelligence_tool,
                url=source.url,
                extraction_focus="product",
                summarize=True,
                detect_changes=bool(source.last_content_hash),
                previous_snapshot_hash=source.last_content_hash,
            )
            return CrawlResult(
                content_hash=result.get("content_hash", ""),
                content_summary=result.get("content_summary", ""),
                extracted_signals=result.get("signals_detected", []),
            )
        except Exception as e:
            return CrawlResult(content_hash="", error=str(e))

    async def extract_signals(self, content: str, company_name: str,
                               hypotheses: list[str] | None = None) -> list[dict]:
        from app.tools.intent_signal_extractor import intent_signal_extractor
        result = intent_signal_extractor(content, signal_hypotheses=hypotheses)
        return result.get("intent_signals", [])


class PressReleaseConnector(SourceConnector):
    """Press release page monitoring — detects funding, partnerships, leadership."""

    async def crawl(self, source: CustomSignalSource) -> CrawlResult:
        import asyncio
        from app.tools.web_intelligence_tool import web_intelligence_tool
        try:
            result = await asyncio.to_thread(
                web_intelligence_tool,
                url=source.url,
                extraction_focus="general",
                summarize=True,
                detect_changes=bool(source.last_content_hash),
                previous_snapshot_hash=source.last_content_hash,
            )
            return CrawlResult(
                content_hash=result.get("content_hash", ""),
                content_summary=result.get("content_summary", ""),
                extracted_signals=result.get("signals_detected", []),
            )
        except Exception as e:
            return CrawlResult(content_hash="", error=str(e))

    async def extract_signals(self, content: str, company_name: str,
                               hypotheses: list[str] | None = None) -> list[dict]:
        from app.tools.intent_signal_extractor import intent_signal_extractor
        result = intent_signal_extractor(content, signal_hypotheses=hypotheses)
        signals = result.get("intent_signals", [])
        # Press releases often contain funding, partnership, or leadership signals
        for s in signals:
            if not s.get("source_class"):
                s["source_class"] = "press_release"
        return signals


class SECFilingConnector(SourceConnector):
    """SEC filing monitoring — parses EDGAR filings for budget and governance signals."""

    async def crawl(self, source: CustomSignalSource) -> CrawlResult:
        import asyncio
        from app.tools.web_intelligence_tool import web_intelligence_tool
        try:
            result = await asyncio.to_thread(
                web_intelligence_tool,
                url=source.url,
                extraction_focus="general",
                summarize=True,
                detect_changes=bool(source.last_content_hash),
                previous_snapshot_hash=source.last_content_hash,
            )
            return CrawlResult(
                content_hash=result.get("content_hash", ""),
                content_summary=result.get("content_summary", ""),
                extracted_signals=[
                    {**s, "source_class": "sec_filing"}
                    for s in result.get("signals_detected", [])
                ],
            )
        except Exception as e:
            return CrawlResult(content_hash="", error=str(e))

    async def extract_signals(self, content: str, company_name: str,
                               hypotheses: list[str] | None = None) -> list[dict]:
        from app.tools.intent_signal_extractor import intent_signal_extractor
        result = intent_signal_extractor(content, signal_hypotheses=hypotheses or [
            "budget allocation", "capital expenditure", "revenue growth",
            "acquisition", "divestiture", "compliance", "risk factor",
        ])
        signals = result.get("intent_signals", [])
        for s in signals:
            s["source_class"] = "sec_filing"
        return signals


class LinkedInConnector(SourceConnector):
    """LinkedIn company page monitoring — detects hiring, leadership, content signals."""

    async def crawl(self, source: CustomSignalSource) -> CrawlResult:
        import asyncio
        from app.tools.web_intelligence_tool import web_intelligence_tool
        try:
            result = await asyncio.to_thread(
                web_intelligence_tool,
                url=source.url,
                extraction_focus="leadership",
                summarize=True,
                detect_changes=bool(source.last_content_hash),
                previous_snapshot_hash=source.last_content_hash,
            )
            return CrawlResult(
                content_hash=result.get("content_hash", ""),
                content_summary=result.get("content_summary", ""),
                extracted_signals=result.get("signals_detected", []),
            )
        except Exception as e:
            return CrawlResult(content_hash="", error=str(e))

    async def extract_signals(self, content: str, company_name: str,
                               hypotheses: list[str] | None = None) -> list[dict]:
        from app.tools.intent_signal_extractor import intent_signal_extractor
        result = intent_signal_extractor(content, signal_hypotheses=hypotheses)
        return result.get("intent_signals", [])


class GitHubConnector(SourceConnector):
    """GitHub organization monitoring — detects tech stack changes and open source activity."""

    async def crawl(self, source: CustomSignalSource) -> CrawlResult:
        import asyncio
        from app.tools.web_intelligence_tool import web_intelligence_tool
        try:
            result = await asyncio.to_thread(
                web_intelligence_tool,
                url=source.url,
                extraction_focus="tech_stack",
                summarize=True,
                detect_changes=bool(source.last_content_hash),
                previous_snapshot_hash=source.last_content_hash,
            )
            return CrawlResult(
                content_hash=result.get("content_hash", ""),
                content_summary=result.get("content_summary", ""),
                extracted_signals=result.get("signals_detected", []),
            )
        except Exception as e:
            return CrawlResult(content_hash="", error=str(e))

    async def extract_signals(self, content: str, company_name: str,
                               hypotheses: list[str] | None = None) -> list[dict]:
        from app.tools.tech_stack_detector import tech_stack_detector
        result = tech_stack_detector(domain="", company_name=company_name)
        signals = []
        for tech in result.get("detected_technologies", []):
            if tech.get("confidence_score", 0) > 0.6:
                signals.append({
                    "signal_type": "tech_adoption",
                    "title": f"{company_name} using {tech['name']}",
                    "strength": int(tech["confidence_score"] * 100),
                    "evidence": tech,
                })
        for migration in result.get("migrations", []):
            signals.append({
                "signal_type": "tech_adoption",
                "title": f"{company_name} migrating from {migration['from']} to {migration['to']}",
                "strength": 75,
                "evidence": migration,
            })
        return signals


class RSSConnector(SourceConnector):
    """RSS feed monitoring — detects new content and announcements."""

    async def crawl(self, source: CustomSignalSource) -> CrawlResult:
        import asyncio
        from app.tools.web_intelligence_tool import web_intelligence_tool
        try:
            result = await asyncio.to_thread(
                web_intelligence_tool,
                url=source.url,
                extraction_focus="general",
                summarize=True,
                detect_changes=bool(source.last_content_hash),
                previous_snapshot_hash=source.last_content_hash,
            )
            return CrawlResult(
                content_hash=result.get("content_hash", ""),
                content_summary=result.get("content_summary", ""),
                extracted_signals=result.get("signals_detected", []),
            )
        except Exception as e:
            return CrawlResult(content_hash="", error=str(e))

    async def extract_signals(self, content: str, company_name: str,
                               hypotheses: list[str] | None = None) -> list[dict]:
        from app.tools.intent_signal_extractor import intent_signal_extractor
        result = intent_signal_extractor(content, signal_hypotheses=hypotheses)
        return result.get("intent_signals", [])


class RedditConnector(SourceConnector):
    """Reddit monitoring — tracks company mentions and community sentiment."""

    async def crawl(self, source: CustomSignalSource) -> CrawlResult:
        import asyncio
        from app.tools.web_intelligence_tool import web_intelligence_tool
        try:
            result = await asyncio.to_thread(
                web_intelligence_tool,
                url=source.url,
                extraction_focus="general",
                summarize=True,
                detect_changes=bool(source.last_content_hash),
                previous_snapshot_hash=source.last_content_hash,
            )
            return CrawlResult(
                content_hash=result.get("content_hash", ""),
                content_summary=result.get("content_summary", ""),
                extracted_signals=[
                    {**s, "source_class": "social_media"}
                    for s in result.get("signals_detected", [])
                ],
            )
        except Exception as e:
            return CrawlResult(content_hash="", error=str(e))

    async def extract_signals(self, content: str, company_name: str,
                               hypotheses: list[str] | None = None) -> list[dict]:
        from app.tools.intent_signal_extractor import intent_signal_extractor
        result = intent_signal_extractor(content, signal_hypotheses=hypotheses)
        signals = result.get("intent_signals", [])
        for s in signals:
            s["source_class"] = "social_media"
        return signals


class YouTubeConnector(SourceConnector):
    """YouTube channel monitoring — detects product demos, webinars, announcements."""

    async def crawl(self, source: CustomSignalSource) -> CrawlResult:
        import asyncio
        from app.tools.web_intelligence_tool import web_intelligence_tool
        try:
            result = await asyncio.to_thread(
                web_intelligence_tool,
                url=source.url,
                extraction_focus="product",
                summarize=True,
                detect_changes=bool(source.last_content_hash),
                previous_snapshot_hash=source.last_content_hash,
            )
            return CrawlResult(
                content_hash=result.get("content_hash", ""),
                content_summary=result.get("content_summary", ""),
                extracted_signals=result.get("signals_detected", []),
            )
        except Exception as e:
            return CrawlResult(content_hash="", error=str(e))

    async def extract_signals(self, content: str, company_name: str,
                               hypotheses: list[str] | None = None) -> list[dict]:
        from app.tools.intent_signal_extractor import intent_signal_extractor
        result = intent_signal_extractor(content, signal_hypotheses=hypotheses)
        return result.get("intent_signals", [])


class ProcurementConnector(SourceConnector):
    """Procurement portal monitoring — detects RFPs, vendor registrations, bid activity."""

    async def crawl(self, source: CustomSignalSource) -> CrawlResult:
        import asyncio
        from app.tools.web_intelligence_tool import web_intelligence_tool
        try:
            result = await asyncio.to_thread(
                web_intelligence_tool,
                url=source.url,
                extraction_focus="general",
                summarize=True,
                detect_changes=bool(source.last_content_hash),
                previous_snapshot_hash=source.last_content_hash,
            )
            return CrawlResult(
                content_hash=result.get("content_hash", ""),
                content_summary=result.get("content_summary", ""),
                extracted_signals=result.get("signals_detected", []),
            )
        except Exception as e:
            return CrawlResult(content_hash="", error=str(e))

    async def extract_signals(self, content: str, company_name: str,
                               hypotheses: list[str] | None = None) -> list[dict]:
        from app.tools.intent_signal_extractor import intent_signal_extractor
        result = intent_signal_extractor(content, signal_hypotheses=[
            "RFP", "request for proposal", "vendor registration",
            "procurement", "bid", "tender", "contract award",
            *(hypotheses or []),
        ])
        signals = result.get("intent_signals", [])
        for s in signals:
            s["source_class"] = "procurement"
        return signals


# Connector registry
CONNECTORS: dict[str, type[SourceConnector]] = {
    "website": WebsiteConnector,
    "careers": CareersPageConnector,
    "blog": BlogConnector,
    "press": PressReleaseConnector,
    "rss": RSSConnector,
    "sec": SECFilingConnector,
    "linkedin": LinkedInConnector,
    "github": GitHubConnector,
    "reddit": RedditConnector,
    "youtube": YouTubeConnector,
    "procurement": ProcurementConnector,
}


def get_connector(source_type: str) -> SourceConnector:
    """Get the appropriate connector for a source type."""
    connector_cls = CONNECTORS.get(source_type, WebsiteConnector)
    return connector_cls()


async def crawl_source(db: AsyncSession, source: CustomSignalSource) -> CrawlResult:
    """Crawl a source, store snapshot, detect changes, extract signals."""
    connector = get_connector(source.source_type)
    result = await connector.crawl(source)

    if result.error:
        logger.warning(f"Crawl failed for source {source.id}: {result.error}")
        return result

    # Check for changes
    has_changes = result.content_hash != (source.last_content_hash or "")

    # Store snapshot
    snapshot = SourceSnapshot(
        source_id=source.id,
        content_hash=result.content_hash,
        content_summary=result.content_summary[:2000] if result.content_summary else None,
        extracted_signals=result.extracted_signals,
    )
    db.add(snapshot)

    # Update source metadata
    source.last_crawled_at = datetime.now(timezone.utc)
    source.last_content_hash = result.content_hash

    if has_changes:
        await bus.emit(Events.SOURCE_CHANGED, {
            "source_id": str(source.id),
            "company_kb_id": str(source.company_kb_id) if source.company_kb_id else None,
            "signals_found": len(result.extracted_signals),
        })

    await bus.emit(Events.SOURCE_CRAWLED, {
        "source_id": str(source.id),
        "has_changes": has_changes,
    })

    await db.flush()
    return result
