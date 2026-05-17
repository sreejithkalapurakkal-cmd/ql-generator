"""Activity Feed API endpoints."""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.services.activity_feed_service import get_activity_feed, get_activity_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("/{company_kb_id}")
async def activity_feed(
    company_kb_id: UUID,
    verbosity: str = Query("summary", description="summary, detailed, or technical"),
    category: Optional[str] = Query(None, description="Filter by category: research, signal, synthesis, contact, outreach"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get activity feed for a company with verbosity filtering."""
    feed, total = await get_activity_feed(
        db, company_kb_id,
        verbosity=verbosity,
        category=category,
        limit=limit,
        offset=offset,
    )
    return {
        "events": feed,
        "total": total,
        "verbosity": verbosity,
        "offset": offset,
        "limit": limit,
    }


@router.get("/{company_kb_id}/stats")
async def activity_stats(
    company_kb_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get activity summary stats for a company."""
    stats = await get_activity_stats(db, company_kb_id)
    return stats
