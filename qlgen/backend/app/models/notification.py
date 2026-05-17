import uuid
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base import Base


class Notification(Base):
    """In-app notification for signal alerts and system events.

    Displayed via bell icon + notification drawer. Each notification
    can optionally link to a SignalEvent and has a deep link within qlGen.
    """
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Optional link to the triggering signal event
    signal_event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("signal_events.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Notification type
    notification_type = Column(String(50), nullable=False)
    # signal_detected, monitoring_complete, ingest_complete, outreach_reminder

    # Content
    title = Column(String(500), nullable=False)
    body = Column(Text)
    link = Column(String(500))  # deep link within qlGen (e.g., /tracking/123/company/456)

    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_notification_user_read_created", "user_id", "is_read", "created_at"),
    )
