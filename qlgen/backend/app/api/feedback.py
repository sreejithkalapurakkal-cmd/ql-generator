"""Feedback and complaints endpoints."""
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.user import User
from app.models.feedback import Feedback, FeedbackReply
from app.schemas.feedback import (
    FeedbackCreate,
    FeedbackStatusUpdate,
    FeedbackReplyCreate,
    FeedbackResponse,
    FeedbackListResponse,
    FeedbackReplyResponse,
)
from app.auth.dependencies import get_current_user, get_current_super_admin
from app.services.audit_service import log_audit

router = APIRouter(prefix="/feedback", tags=["Feedback"])


def _build_reply_response(reply: FeedbackReply) -> FeedbackReplyResponse:
    return FeedbackReplyResponse(
        id=reply.id,
        feedback_id=reply.feedback_id,
        user_id=reply.user_id,
        user_name=reply.user.name if reply.user else None,
        user_email=reply.user.email if reply.user else None,
        message=reply.message,
        created_at=reply.created_at,
    )


def _build_feedback_response(fb: Feedback) -> FeedbackResponse:
    return FeedbackResponse(
        id=fb.id,
        user_id=fb.user_id,
        user_name=fb.user.name if fb.user else None,
        user_email=fb.user.email if fb.user else None,
        type=fb.type,
        subject=fb.subject,
        description=fb.description,
        status=fb.status,
        created_at=fb.created_at,
        updated_at=fb.updated_at,
        replies=[_build_reply_response(r) for r in fb.replies],
    )


def _build_list_response(fb: Feedback) -> FeedbackListResponse:
    return FeedbackListResponse(
        id=fb.id,
        user_id=fb.user_id,
        user_name=fb.user.name if fb.user else None,
        user_email=fb.user.email if fb.user else None,
        type=fb.type,
        subject=fb.subject,
        status=fb.status,
        reply_count=len(fb.replies),
        created_at=fb.created_at,
        updated_at=fb.updated_at,
    )


@router.post("", response_model=FeedbackResponse)
async def create_feedback(
    body: FeedbackCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit new feedback or complaint."""
    fb = Feedback(
        user_id=user.id,
        type=body.type,
        subject=body.subject,
        description=body.description,
        status="open",
    )
    db.add(fb)
    await db.commit()

    await log_audit(
        db, user.id, "create", "feedback",
        resource_id=fb.id,
        details={"type": body.type, "subject": body.subject},
        ip_address=request.client.host if request.client else None,
    )

    # Re-fetch with eager loading for the response
    result = await db.execute(
        select(Feedback)
        .options(
            selectinload(Feedback.user),
            selectinload(Feedback.replies),
        )
        .where(Feedback.id == fb.id)
    )
    fb = result.scalar_one()

    return _build_feedback_response(fb)


@router.get("", response_model=list[FeedbackListResponse])
async def list_feedback(
    type_filter: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List feedback. Regular users see their own; super_admin sees all."""
    query = (
        select(Feedback)
        .options(selectinload(Feedback.user), selectinload(Feedback.replies))
        .order_by(Feedback.created_at.desc())
    )

    if user.role != "super_admin":
        query = query.where(Feedback.user_id == user.id)

    if type_filter:
        query = query.where(Feedback.type == type_filter)
    if status_filter:
        query = query.where(Feedback.status == status_filter)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()

    return [_build_list_response(fb) for fb in items]


@router.get("/{feedback_id}", response_model=FeedbackResponse)
async def get_feedback(
    feedback_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single feedback item with its replies."""
    result = await db.execute(
        select(Feedback)
        .options(
            selectinload(Feedback.user),
            selectinload(Feedback.replies).selectinload(FeedbackReply.user),
        )
        .where(Feedback.id == feedback_id)
    )
    fb = result.scalar_one_or_none()

    if not fb:
        raise HTTPException(status_code=404, detail="Feedback not found")

    if user.role != "super_admin" and fb.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return _build_feedback_response(fb)


@router.put("/{feedback_id}/status", response_model=FeedbackResponse)
async def update_feedback_status(
    feedback_id: UUID,
    body: FeedbackStatusUpdate,
    request: Request,
    admin: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update feedback status (super_admin only)."""
    result = await db.execute(
        select(Feedback)
        .options(
            selectinload(Feedback.user),
            selectinload(Feedback.replies).selectinload(FeedbackReply.user),
        )
        .where(Feedback.id == feedback_id)
    )
    fb = result.scalar_one_or_none()

    if not fb:
        raise HTTPException(status_code=404, detail="Feedback not found")

    old_status = fb.status
    fb.status = body.status
    await db.commit()

    await log_audit(
        db, admin.id, "update_status", "feedback",
        resource_id=fb.id,
        details={"old_status": old_status, "new_status": body.status},
        ip_address=request.client.host if request.client else None,
    )

    # Re-fetch with eager loading for the response
    result2 = await db.execute(
        select(Feedback)
        .options(
            selectinload(Feedback.user),
            selectinload(Feedback.replies).selectinload(FeedbackReply.user),
        )
        .where(Feedback.id == feedback_id)
    )
    fb = result2.scalar_one()

    return _build_feedback_response(fb)


@router.post("/{feedback_id}/reply", response_model=FeedbackReplyResponse)
async def reply_to_feedback(
    feedback_id: UUID,
    body: FeedbackReplyCreate,
    request: Request,
    admin: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Add an admin reply to feedback (super_admin only)."""
    result = await db.execute(select(Feedback).where(Feedback.id == feedback_id))
    fb = result.scalar_one_or_none()

    if not fb:
        raise HTTPException(status_code=404, detail="Feedback not found")

    reply = FeedbackReply(
        feedback_id=fb.id,
        user_id=admin.id,
        message=body.message,
    )
    db.add(reply)
    await db.commit()

    await log_audit(
        db, admin.id, "reply", "feedback",
        resource_id=fb.id,
        details={"reply_id": str(reply.id)},
        ip_address=request.client.host if request.client else None,
    )

    # Re-fetch with eager loading for the response
    result = await db.execute(
        select(FeedbackReply)
        .options(selectinload(FeedbackReply.user))
        .where(FeedbackReply.id == reply.id)
    )
    reply = result.scalar_one()

    return _build_reply_response(reply)
