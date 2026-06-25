"""Accounts API endpoints.

Provides a unified listing of all companies in the user's tracking lists
with filtering, sorting, and aggregated signal/brief/draft counts.
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.company_knowledge_base import CompanyKnowledgeBase
from app.models.tracking_list import TrackingList
from app.models.tracking_list_membership import TrackingListMembership
from app.models.signal_event import SignalEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("")
async def list_accounts(
    search: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    sort_by: str = Query("signal_count", description="signal_count, name, industry"),
    sort_dir: str = Query("desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all accounts (companies) across the user's tracking lists."""
    # Get user's tracked company KB IDs
    list_result = await db.execute(
        select(TrackingList.id).where(
            TrackingList.user_id == user.id,
            TrackingList.is_active == True,
        )
    )
    list_ids = [row[0] for row in list_result.all()]
    if not list_ids:
        return {"accounts": [], "total": 0}

    membership_result = await db.execute(
        select(TrackingListMembership.company_kb_id).where(
            TrackingListMembership.tracking_list_id.in_(list_ids)
        ).distinct()
    )
    kb_ids = [row[0] for row in membership_result.all()]
    if not kb_ids:
        return {"accounts": [], "total": 0}

    # Subquery: signal count per company
    signal_count_sq = (
        select(
            SignalEvent.company_kb_id,
            func.count(SignalEvent.id).label("sig_count"),
        )
        .where(
            SignalEvent.is_archived == False,
            SignalEvent.is_dismissed == False,
            SignalEvent.is_relevant.isnot(False),  # hide validator-rejected signals
        )
        .group_by(SignalEvent.company_kb_id)
        .subquery()
    )

    # Main query
    query = (
        select(
            CompanyKnowledgeBase,
            func.coalesce(signal_count_sq.c.sig_count, 0).label("signal_count"),
        )
        .outerjoin(signal_count_sq, CompanyKnowledgeBase.id == signal_count_sq.c.company_kb_id)
        .where(CompanyKnowledgeBase.id.in_(kb_ids))
    )

    count_query = (
        select(func.count(CompanyKnowledgeBase.id))
        .where(CompanyKnowledgeBase.id.in_(kb_ids))
    )

    # Filters
    if search:
        search_filter = f"%{search.lower()}%"
        query = query.where(
            func.lower(func.coalesce(CompanyKnowledgeBase.canonical_name, "")).like(search_filter)
            | func.lower(func.coalesce(CompanyKnowledgeBase.normalized_domain, "")).like(search_filter)
        )
        count_query = count_query.where(
            func.lower(func.coalesce(CompanyKnowledgeBase.canonical_name, "")).like(search_filter)
            | func.lower(func.coalesce(CompanyKnowledgeBase.normalized_domain, "")).like(search_filter)
        )
    if industry:
        query = query.where(CompanyKnowledgeBase.industry == industry)
        count_query = count_query.where(CompanyKnowledgeBase.industry == industry)
    if country:
        query = query.where(CompanyKnowledgeBase.country == country)
        count_query = count_query.where(CompanyKnowledgeBase.country == country)
    if status:
        query = query.where(CompanyKnowledgeBase.status == status)
        count_query = count_query.where(CompanyKnowledgeBase.status == status)

    total = (await db.execute(count_query)).scalar() or 0

    # Sort
    if sort_by == "name":
        order_col = CompanyKnowledgeBase.canonical_name
    elif sort_by == "industry":
        order_col = CompanyKnowledgeBase.industry
    else:
        order_col = func.coalesce(signal_count_sq.c.sig_count, 0)

    if sort_dir == "asc":
        query = query.order_by(order_col.asc())
    else:
        query = query.order_by(order_col.desc())

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    rows = result.all()

    accounts = []
    for kb, sig_count in rows:
        accounts.append({
            "id": str(kb.id),
            "name": kb.canonical_name,
            "domain": kb.normalized_domain,
            "industry": kb.industry,
            "sub_industry": kb.sub_industry,
            "country": kb.country,
            "region": kb.country,
            "employee_count": kb.employee_count,
            "status": kb.status or "monitored",
            "signal_count": sig_count,
            "has_brief": kb.has_brief or False,
            "open_draft_count": kb.open_draft_count or 0,
            "tags": kb.tags or [],
            "icp_fit": (
                "strong" if (kb.best_icp_match_score or 0) >= 70
                else "moderate" if (kb.best_icp_match_score or 0) >= 40
                else "weak" if kb.best_icp_match_score is not None
                else None
            ),
            "icp_score": kb.best_icp_match_score,
        })

    return {
        "accounts": accounts,
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/{account_id}")
async def get_account_detail(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get detailed account profile including signals, brief status, and contacts."""
    result = await db.execute(
        select(CompanyKnowledgeBase).where(CompanyKnowledgeBase.id == account_id)
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Account not found")

    # Signal count
    sig_result = await db.execute(
        select(func.count(SignalEvent.id)).where(
            SignalEvent.company_kb_id == account_id,
            SignalEvent.is_archived == False,
            SignalEvent.is_dismissed == False,
            SignalEvent.is_relevant.isnot(False),  # hide validator-rejected signals
        )
    )
    signal_count = sig_result.scalar() or 0

    # Recent signals (top 5)
    recent_signals_result = await db.execute(
        select(SignalEvent).where(
            SignalEvent.company_kb_id == account_id,
            SignalEvent.is_archived == False,
            SignalEvent.is_dismissed == False,
            SignalEvent.is_relevant.isnot(False),  # hide validator-rejected signals
        ).order_by(SignalEvent.created_at.desc()).limit(5)
    )
    recent_signals = [
        {
            "id": str(s.id),
            "signal_type": s.signal_type,
            "priority": s.priority,
            "title": s.title,
            "summary": s.summary,
            "confidence": s.confidence,
            "detected_at": s.detected_at.isoformat() if s.detected_at else None,
        }
        for s in recent_signals_result.scalars().all()
    ]

    # Brief info
    from app.models.brief_revision import BriefRevision
    brief_result = await db.execute(
        select(BriefRevision).where(
            BriefRevision.company_kb_id == account_id
        ).order_by(BriefRevision.version.desc()).limit(1)
    )
    latest_brief = brief_result.scalar_one_or_none()

    # Draft count
    from app.models.draft import Draft
    draft_result = await db.execute(
        select(func.count(Draft.id)).where(
            Draft.company_kb_id == account_id,
            Draft.status == "in_progress",
        )
    )
    draft_count = draft_result.scalar() or 0

    # Contacts
    contacts = kb.best_known_contacts or []

    return {
        "id": str(kb.id),
        "name": kb.canonical_name,
        "domain": kb.normalized_domain,
        "industry": kb.industry,
        "sub_industry": kb.sub_industry,
        "country": kb.country,
        "city": kb.city,
        "employee_count": kb.employee_count,
        "revenue_estimate": kb.revenue_estimate,
        "description": kb.description,
        "status": kb.status or "monitored",
        "owner": kb.owner,
        "tags": kb.tags or [],
        "signal_count": signal_count,
        "recent_signals": recent_signals,
        "has_brief": latest_brief is not None,
        "latest_brief_version": latest_brief.version if latest_brief else None,
        "open_draft_count": draft_count,
        "contact_count": len(contacts),
        "contacts": [
            {
                "id": c.get("id", str(i)),
                "name": c.get("full_name") or c.get("name", ""),
                "title": c.get("designation") or c.get("title", ""),
                "email": c.get("email"),
                "linkedin_url": c.get("linkedin_url"),
            }
            for i, c in enumerate(contacts[:10])
        ],
    }


@router.patch("/{account_id}")
async def update_account(
    account_id: UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update account status, tags, or owner."""
    result = await db.execute(
        select(CompanyKnowledgeBase).where(CompanyKnowledgeBase.id == account_id)
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Account not found")

    if "status" in payload:
        kb.status = payload["status"]
    if "owner" in payload:
        kb.owner = payload["owner"]
    if "tags" in payload:
        kb.tags = payload["tags"]

    await db.commit()
    return {
        "id": str(kb.id),
        "status": kb.status,
        "owner": kb.owner,
        "tags": kb.tags,
    }
