import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base import Base


class SignalDetectionRun(Base):
    """Tracks a background signal detection task for a tracking list.

    Lifecycle: pending → running → completed/failed/cancelled.
    """
    __tablename__ = "signal_detection_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tracking_list_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tracking_lists.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    status = Column(String(50), default="pending")  # pending, running, completed, failed, cancelled
    total_companies = Column(Integer, default=0)
    processed_companies = Column(Integer, default=0)
    signals_detected = Column(Integer, default=0)
    use_agent = Column(Boolean, default=False)  # True = dedicated signal research agent
    error_log = Column(Text, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_sigdetrun_list_created", "tracking_list_id", "created_at"),
        Index("ix_sigdetrun_user", "user_id"),
    )
