"""Notification API endpoints."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.services.notification_service import (
    get_unread_count,
    get_notifications,
    mark_read,
    mark_all_read,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


class MarkReadRequest(BaseModel):
    notification_ids: list[str]


@router.get("/unread-count")
async def unread_count(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    count = await get_unread_count(db, user.id)
    return {"unread_count": count}


@router.get("")
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    notifs, total = await get_notifications(
        db, user.id, limit=limit, offset=offset, unread_only=unread_only,
    )
    return {
        "notifications": [
            {
                "id": str(n.id),
                "notification_type": n.notification_type,
                "title": n.title,
                "body": n.body,
                "link": n.link,
                "is_read": n.is_read,
                "signal_event_id": str(n.signal_event_id) if n.signal_event_id else None,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notifs
        ],
        "total": total,
    }


@router.post("/mark-read")
async def mark_notifications_read(
    request: MarkReadRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ids = [UUID(nid) for nid in request.notification_ids]
    count = await mark_read(db, ids)
    await db.commit()
    return {"marked_read": count}


@router.post("/mark-all-read")
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    count = await mark_all_read(db, user.id)
    await db.commit()
    return {"marked_read": count}
