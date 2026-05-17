import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db.base import Base


class IngestBatchLog(Base):
    """Persists SSE events for ingest batch processing (import + firmographic evaluation).

    Mirrors PipelineLog — enables replay on page revisit and audit trail.
    """
    __tablename__ = "ingest_batch_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ingest_batch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ingest_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type = Column(String(50), nullable=False)
    event_data = Column(JSONB, nullable=False)
    sequence_number = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_ingest_batch_log_batch_seq", "ingest_batch_id", "sequence_number"),
    )
