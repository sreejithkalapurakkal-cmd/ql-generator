import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db.base import Base


class IngestBatch(Base):
    """Tracks a file upload / paste ingestion of companies.

    Separate from PipelineRun — the pipeline has 5-stage assumptions
    that don't apply to ingestion. IngestBatch has its own lifecycle:
    pending → processing → completed/failed.
    """
    __tablename__ = "ingest_batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Source info
    name = Column(String(255))  # user-given name for this batch
    filename = Column(String(500))
    file_type = Column(String(20), nullable=False)  # xlsx, csv, paste

    # Processing state
    status = Column(String(50), default="pending")  # pending, processing, completed, failed

    # Column mapping: {source_col: target_field}
    column_mapping = Column(JSONB)

    # Filter criteria (dynamic, not tied to ICPConfig schema)
    # Schema varies by list purpose: conference, CRM export, target accounts, etc.
    filter_config = Column(JSONB)

    # Progress counters
    total_rows = Column(Integer, default=0)
    processed_rows = Column(Integer, default=0)
    matched_kb = Column(Integer, default=0)  # matched existing KB records
    newly_created = Column(Integer, default=0)  # new KB stubs created
    enriched_count = Column(Integer, default=0)
    filtered_count = Column(Integer, default=0)  # survived filtering

    # Error details
    errors = Column(JSONB, default=list)  # [{row: int, error: str}]

    # Signal hypotheses for post-ingest detection
    # Schema: {budget_signals: str[], urgency_signals: str[], custom_hints: str[]}
    signal_hypotheses = Column(JSONB, nullable=True)

    # Optional: target tracking list for auto-promotion
    target_tracking_list_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tracking_lists.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    dismissed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_ingest_user_created", "user_id", "created_at"),
        Index("ix_ingest_status", "status"),
    )
