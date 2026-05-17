import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db.base import Base


class EnrichmentLog(Base):
    """Persists SSE events for contact enrichment runs.

    Enables replay on page revisit and audit trail for enrichment activity.
    """
    __tablename__ = "enrichment_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enrichment_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("enrichment_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type = Column(String(50), nullable=False)
    event_data = Column(JSONB, nullable=False)
    sequence_number = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_enrich_log_run_seq", "enrichment_run_id", "sequence_number"),
    )
