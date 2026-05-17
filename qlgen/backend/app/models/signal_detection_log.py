import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db.base import Base


class SignalDetectionLog(Base):
    """Persists SSE events for signal detection runs.

    Enables replay on page revisit and audit trail for detection activity.
    """
    __tablename__ = "signal_detection_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signal_detection_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("signal_detection_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type = Column(String(50), nullable=False)
    event_data = Column(JSONB, nullable=False)
    sequence_number = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_sigdet_log_run_seq", "signal_detection_run_id", "sequence_number"),
    )
