"""Tracking List service.

CRUD operations for tracking lists and memberships. Handles
adding/removing companies, outreach status management, and
signal heat computation.
"""
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.tracking_list import TrackingList
from app.models.tracking_list_membership import TrackingListMembership
from app.models.company_knowledge_base import CompanyKnowledgeBase
from app.models.signal_event import SignalEvent

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# Tracking List CRUD
# ──────────────────────────────────────────────────────────────────

async def create_tracking_list(
    db: AsyncSession,
    user_id: UUID,
    name: str,
    description: str | None = None,
    signal_hints: dict | None = None,
) -> TrackingList:
    tracking_list = TrackingList(
        user_id=user_id,
        name=name,
        description=description,
        signal_hints=signal_hints or {},
    )
    db.add(tracking_list)
    await db.flush()
    return tracking_list


async def get_tracking_lists(
    db: AsyncSession,
    user_id: UUID,
) -> list[TrackingList]:
    result = await db.execute(
        select(TrackingList)
        .where(TrackingList.user_id == user_id, TrackingList.is_active == True)
        .order_by(TrackingList.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_tracking_list(
    db: AsyncSession,
    list_id: UUID,
    user_id: UUID,
) -> TrackingList | None:
    result = await db.execute(
        select(TrackingList).where(
            TrackingList.id == list_id,
            TrackingList.user_id == user_id,
            TrackingList.is_active == True,
        )
    )
    return result.scalar_one_or_none()


async def update_tracking_list(
    db: AsyncSession,
    list_id: UUID,
    user_id: UUID,
    name: str | None = None,
    description: str | None = None,
    monitoring_config: dict | None = None,
    signal_hints: dict | None = None,
) -> TrackingList | None:
    tracking_list = await get_tracking_list(db, list_id, user_id)
    if not tracking_list:
        return None

    if name is not None:
        tracking_list.name = name
    if description is not None:
        tracking_list.description = description
    if monitoring_config is not None:
        tracking_list.monitoring_config = monitoring_config
    if signal_hints is not None:
        tracking_list.signal_hints = signal_hints

    await db.flush()
    return tracking_list


async def delete_tracking_list(
    db: AsyncSession,
    list_id: UUID,
    user_id: UUID,
) -> bool:
    tracking_list = await get_tracking_list(db, list_id, user_id)
    if not tracking_list:
        return False

    tracking_list.is_active = False
    await db.flush()
    return True


# ──────────────────────────────────────────────────────────────────
# Membership management
# ──────────────────────────────────────────────────────────────────

async def add_companies_to_list(
    db: AsyncSession,
    list_id: UUID,
    user_id: UUID,
    company_kb_ids: list[UUID],
    added_from: str = "manual",
) -> list[TrackingListMembership]:
    """Add companies to a tracking list. Deduplicates by (list_id, kb_id)."""
    tracking_list = await get_tracking_list(db, list_id, user_id)
    if not tracking_list:
        return []

    # Find existing memberships to avoid duplicates
    existing = await db.execute(
        select(TrackingListMembership.company_kb_id).where(
            TrackingListMembership.tracking_list_id == list_id,
            TrackingListMembership.company_kb_id.in_(company_kb_ids),
        )
    )
    existing_ids = {row[0] for row in existing.all()}

    new_memberships = []
    for kb_id in company_kb_ids:
        if kb_id in existing_ids:
            continue

        membership = TrackingListMembership(
            tracking_list_id=list_id,
            company_kb_id=kb_id,
            added_from=added_from,
        )
        db.add(membership)
        new_memberships.append(membership)

    # Update company count
    tracking_list.company_count = (tracking_list.company_count or 0) + len(new_memberships)

    await db.flush()
    return new_memberships


async def remove_companies_from_list(
    db: AsyncSession,
    list_id: UUID,
    user_id: UUID,
    membership_ids: list[UUID],
) -> int:
    """Remove companies from a tracking list by membership IDs."""
    tracking_list = await get_tracking_list(db, list_id, user_id)
    if not tracking_list:
        return 0

    result = await db.execute(
        delete(TrackingListMembership).where(
            TrackingListMembership.id.in_(membership_ids),
            TrackingListMembership.tracking_list_id == list_id,
        )
    )
    removed = result.rowcount

    # Update company count
    count_result = await db.execute(
        select(func.count(TrackingListMembership.id)).where(
            TrackingListMembership.tracking_list_id == list_id
        )
    )
    tracking_list.company_count = count_result.scalar() or 0

    await db.flush()
    return removed


async def get_list_members(
    db: AsyncSession,
    list_id: UUID,
    user_id: UUID,
    outreach_status: str | None = None,
    search: str | None = None,
    industry_filter: str | None = None,
    sort_by: str = "signal_heat_score",
    sort_order: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Get tracking list members with joined KB data and latest signal.

    Returns (members, total_count).
    """
    tracking_list = await get_tracking_list(db, list_id, user_id)
    if not tracking_list:
        return [], 0

    # Base query joining membership with KB
    query = (
        select(TrackingListMembership, CompanyKnowledgeBase)
        .join(
            CompanyKnowledgeBase,
            TrackingListMembership.company_kb_id == CompanyKnowledgeBase.id,
        )
        .where(TrackingListMembership.tracking_list_id == list_id)
    )

    if outreach_status:
        query = query.where(TrackingListMembership.outreach_status == outreach_status)
    if search:
        query = query.where(CompanyKnowledgeBase.canonical_name.ilike(f"%{search}%"))
    if industry_filter:
        query = query.where(CompanyKnowledgeBase.industry == industry_filter)

    # Count before pagination
    count_query = (
        select(func.count(TrackingListMembership.id))
        .join(
            CompanyKnowledgeBase,
            TrackingListMembership.company_kb_id == CompanyKnowledgeBase.id,
        )
        .where(TrackingListMembership.tracking_list_id == list_id)
    )
    if outreach_status:
        count_query = count_query.where(TrackingListMembership.outreach_status == outreach_status)
    if search:
        count_query = count_query.where(CompanyKnowledgeBase.canonical_name.ilike(f"%{search}%"))
    if industry_filter:
        count_query = count_query.where(CompanyKnowledgeBase.industry == industry_filter)
    total = (await db.execute(count_query)).scalar() or 0

    # Sort
    sort_map = {
        "signal_heat_score": TrackingListMembership.signal_heat_score,
        "added_at": TrackingListMembership.added_at,
        "outreach_status": TrackingListMembership.outreach_status,
        "company_name": CompanyKnowledgeBase.canonical_name,
        "best_final_score": CompanyKnowledgeBase.best_final_score,
    }
    sort_col = sort_map.get(sort_by, TrackingListMembership.signal_heat_score)
    if sort_order == "asc":
        query = query.order_by(sort_col.asc().nullslast())
    else:
        query = query.order_by(sort_col.desc().nullslast())

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    rows = result.all()

    members = []
    for membership, kb in rows:
        # Get latest signal for this company (by evidence freshness, not discovery time)
        from sqlalchemy import func as sa_func
        latest_signal_result = await db.execute(
            select(SignalEvent)
            .where(
                SignalEvent.company_kb_id == kb.id,
                SignalEvent.is_archived == False,
                SignalEvent.is_dismissed == False,
            )
            .order_by(sa_func.coalesce(SignalEvent.evidence_date, SignalEvent.detected_at).desc())
            .limit(1)
        )
        latest_signal = latest_signal_result.scalar_one_or_none()

        members.append({
            "membership_id": str(membership.id),
            "company_kb_id": str(kb.id),
            "company_name": kb.canonical_name,
            "domain": kb.normalized_domain,
            "industry": kb.industry,
            "country": kb.country,
            "city": kb.city,
            "employee_count": kb.employee_count,
            "revenue_estimate": kb.revenue_estimate,
            "best_final_score": kb.best_final_score,
            "best_deal_hotness_tier": kb.best_deal_hotness_tier,
            "signal_heat_score": membership.signal_heat_score,
            "outreach_status": membership.outreach_status,
            "outreach_history": membership.outreach_history,
            "notes": membership.notes,
            "tags": membership.tags,
            "added_from": membership.added_from,
            "added_at": membership.added_at.isoformat() if membership.added_at else None,
            "snoozed_until": membership.snoozed_until.isoformat() if membership.snoozed_until else None,
            "latest_signal": {
                "id": str(latest_signal.id),
                "signal_type": latest_signal.signal_type,
                "priority": latest_signal.priority,
                "title": latest_signal.title,
                "detected_at": latest_signal.detected_at.isoformat() if latest_signal.detected_at else None,
                "evidence_date": latest_signal.evidence_date.isoformat() if latest_signal.evidence_date else None,
                "source_url": latest_signal.source_url,
            } if latest_signal else None,
            "enrichment_status": membership.enrichment_status or "not_started",
            "best_known_contacts": kb.best_known_contacts,
            "last_enriched_at": kb.last_enriched_at.isoformat() if kb.last_enriched_at else None,
        })

    return members, total


async def update_membership(
    db: AsyncSession,
    list_id: UUID,
    membership_id: UUID,
    user_id: UUID,
    outreach_status: str | None = None,
    notes: str | None = None,
    tags: list | None = None,
    snoozed_until: datetime | None = None,
) -> TrackingListMembership | None:
    """Update a membership's outreach status, notes, tags, or snooze."""
    tracking_list = await get_tracking_list(db, list_id, user_id)
    if not tracking_list:
        return None

    result = await db.execute(
        select(TrackingListMembership).where(
            TrackingListMembership.id == membership_id,
            TrackingListMembership.tracking_list_id == list_id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        return None

    if outreach_status is not None and outreach_status != membership.outreach_status:
        # Log status change in outreach_history
        history = list(membership.outreach_history or [])
        history.append({
            "status": outreach_status,
            "previous_status": membership.outreach_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        membership.outreach_history = history
        membership.outreach_status = outreach_status

    if notes is not None:
        membership.notes = notes
    if tags is not None:
        membership.tags = tags
    if snoozed_until is not None:
        membership.snoozed_until = snoozed_until

    await db.flush()
    return membership


# ──────────────────────────────────────────────────────────────────
# Outreach status summary (for Kanban view)
# ──────────────────────────────────────────────────────────────────

async def get_outreach_summary(
    db: AsyncSession,
    list_id: UUID,
    user_id: UUID,
) -> dict[str, int]:
    """Count members by outreach status for Kanban view."""
    tracking_list = await get_tracking_list(db, list_id, user_id)
    if not tracking_list:
        return {}

    result = await db.execute(
        select(
            TrackingListMembership.outreach_status,
            func.count(TrackingListMembership.id),
        )
        .where(TrackingListMembership.tracking_list_id == list_id)
        .group_by(TrackingListMembership.outreach_status)
    )

    return {row[0]: row[1] for row in result.all()}
