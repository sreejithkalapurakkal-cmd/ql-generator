"""Notification service.

Creates, fetches, and manages in-app notifications.
Notifications are generated when signals are detected or
system events occur (ingest complete, monitoring complete).
"""
import logging
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification

logger = logging.getLogger(__name__)


async def create_notification(
    db: AsyncSession,
    user_id: UUID,
    notification_type: str,
    title: str,
    body: str | None = None,
    link: str | None = None,
    signal_event_id: UUID | None = None,
) -> Notification:
    notif = Notification(
        user_id=user_id,
        signal_event_id=signal_event_id,
        notification_type=notification_type,
        title=title,
        body=body,
        link=link,
    )
    db.add(notif)
    await db.flush()
    return notif


async def get_unread_count(db: AsyncSession, user_id: UUID) -> int:
    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.is_read == False,
        )
    )
    return result.scalar() or 0


async def get_notifications(
    db: AsyncSession,
    user_id: UUID,
    limit: int = 30,
    offset: int = 0,
    unread_only: bool = False,
) -> tuple[list[Notification], int]:
    query = select(Notification).where(Notification.user_id == user_id)
    count_query = select(func.count(Notification.id)).where(Notification.user_id == user_id)

    if unread_only:
        query = query.where(Notification.is_read == False)
        count_query = count_query.where(Notification.is_read == False)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)

    return list(result.scalars().all()), total


async def mark_read(db: AsyncSession, notification_ids: list[UUID]) -> int:
    result = await db.execute(
        update(Notification)
        .where(Notification.id.in_(notification_ids))
        .values(is_read=True)
    )
    await db.flush()
    return result.rowcount


async def mark_all_read(db: AsyncSession, user_id: UUID) -> int:
    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)
        .values(is_read=True)
    )
    await db.flush()
    return result.rowcount
