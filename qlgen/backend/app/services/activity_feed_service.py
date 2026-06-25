"""Activity Feed service.

Provides filtered, paginated access to activity events with
verbosity levels (summary/detailed/technical) and category filtering.
"""
import logging
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_event import ActivityEvent

logger = logging.getLogger(__name__)

# Verbosity hierarchy: summary shows milestones only, detailed shows all non-technical,
# technical shows everything
VERBOSITY_LEVELS = ("summary", "detailed", "technical")


async def get_activity_feed(
    db: AsyncSession,
    company_kb_id: UUID,
    verbosity: str = "summary",
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Get activity feed for a company filtered by verbosity level.

    Verbosity levels:
      - summary: Only milestones (research_start, brief_ready, correlation_found, research_complete)
      - detailed: All non-technical events (includes tool_call, signal_detected, etc.)
      - technical: Everything including raw tool call data
    """
    base_filters = [ActivityEvent.company_kb_id == company_kb_id]

    if verbosity == "summary":
        base_filters.append(ActivityEvent.milestone == True)
    elif verbosity == "detailed":
        # Everything except pure technical noise
        base_filters.append(
            ActivityEvent.verbosity_level.in_(["summary", "detailed"])
            | ActivityEvent.milestone == True
        )
    # technical = no filter (show everything)

    if category:
        base_filters.append(ActivityEvent.event_category == category)

    # Count
    count_result = await db.execute(
        select(func.count(ActivityEvent.id)).where(*base_filters)
    )
    total = count_result.scalar() or 0

    # Fetch
    result = await db.execute(
        select(ActivityEvent)
        .where(*base_filters)
        .order_by(ActivityEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    events = list(result.scalars().all())

    feed = []
    for event in events:
        item = {
            "id": str(event.id),
            "event_type": event.event_type,
            "event_category": event.event_category,
            "narrative": event.narrative,
            "milestone": event.milestone,
            "confidence": event.confidence,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }
        # Include detail fields based on verbosity
        if verbosity in ("detailed", "technical"):
            item["narrative_detail"] = event.narrative_detail
        if verbosity == "technical":
            item["technical_detail"] = event.technical_detail
            item["research_job_id"] = str(event.research_job_id) if event.research_job_id else None

        feed.append(item)

    return feed, total


async def get_activity_by_job(
    db: AsyncSession,
    research_job_id: UUID,
    verbosity: str = "summary",
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Get activity feed for a specific research job.

    Same verbosity/category filtering as get_activity_feed but scoped to a research job.
    """
    base_filters = [ActivityEvent.research_job_id == research_job_id]

    if verbosity == "summary":
        base_filters.append(ActivityEvent.milestone == True)
    elif verbosity == "detailed":
        base_filters.append(
            ActivityEvent.verbosity_level.in_(["summary", "detailed"])
            | ActivityEvent.milestone == True
        )

    if category:
        base_filters.append(ActivityEvent.event_category == category)

    count_result = await db.execute(
        select(func.count(ActivityEvent.id)).where(*base_filters)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(ActivityEvent)
        .where(*base_filters)
        .order_by(ActivityEvent.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    events = list(result.scalars().all())

    feed = []
    for event in events:
        item = {
            "id": str(event.id),
            "event_type": event.event_type,
            "event_category": event.event_category,
            "narrative": event.narrative,
            "milestone": event.milestone,
            "confidence": event.confidence,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }
        if verbosity in ("detailed", "technical"):
            item["narrative_detail"] = event.narrative_detail
        if verbosity == "technical":
            item["technical_detail"] = event.technical_detail
            item["company_kb_id"] = str(event.company_kb_id) if event.company_kb_id else None

        feed.append(item)

    return feed, total


async def get_activity_stats(
    db: AsyncSession,
    company_kb_id: UUID,
) -> dict:
    """Get activity summary stats for a company. Cached for 120 seconds."""
    from app.services.cache_service import cache_get, cache_set
    cache_key = f"activity_stats:{company_kb_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    total = (await db.execute(
        select(func.count(ActivityEvent.id)).where(
            ActivityEvent.company_kb_id == company_kb_id,
        )
    )).scalar() or 0

    milestones = (await db.execute(
        select(func.count(ActivityEvent.id)).where(
            ActivityEvent.company_kb_id == company_kb_id,
            ActivityEvent.milestone == True,
        )
    )).scalar() or 0

    # Category breakdown
    cat_result = await db.execute(
        select(ActivityEvent.event_category, func.count(ActivityEvent.id))
        .where(ActivityEvent.company_kb_id == company_kb_id)
        .group_by(ActivityEvent.event_category)
    )
    by_category = {row[0]: row[1] for row in cat_result.all() if row[0]}

    result = {
        "total_events": total,
        "milestones": milestones,
        "by_category": by_category,
    }

    cache_set(cache_key, result, ttl=120)
    return result
