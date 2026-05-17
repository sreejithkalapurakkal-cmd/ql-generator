import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db.base import Base


class EnrichmentRun(Base):
    """Tracks a background contact enrichment task for a tracking list.

    Lifecycle: pending -> running -> completed/failed/cancelled.
    """
    __tablename__ = "enrichment_runs"

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
    contacts_found = Column(Integer, default=0)
    target_roles = Column(JSONB, nullable=True)
    error_log = Column(Text, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_enrichrun_list_created", "tracking_list_id", "created_at"),
        Index("ix_enrichrun_user", "user_id"),
    )
