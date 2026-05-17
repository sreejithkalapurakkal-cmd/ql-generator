import uuid
from sqlalchemy import Column, String, Text, Float, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db.base import Base


class SignalEvent(Base):
    """First-class signal occurrence for a tracked company.

    Signals are anchored to CompanyKnowledgeBase (real-world company),
    not per-run Company records. They have their own lifecycle: created,
    read, dismissed, archived, expired.

    Signal types: funding, hiring_surge, executive_change,
    champion_job_change, tech_adoption, product_launch, earnings_report,
    press_mention, partnership, expansion, competitor_adoption,
    competitor_churn.
    """
    __tablename__ = "signal_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_kb_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_knowledge_base.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Signal classification
    signal_type = Column(String(50), nullable=False)
    signal_subtype = Column(String(100))  # e.g., "series_b", "new_cto", "aws_migration"
    signal_category = Column(String(50))  # financial, personnel, product, event, intent
    priority = Column(String(20), nullable=False, default="medium")  # critical, high, medium, low
    strength = Column(Float, default=50.0)  # 0-100

    # Human-readable content
    title = Column(String(500), nullable=False)
    summary = Column(Text)

    # Evidence and provenance
    evidence = Column(JSONB)  # source data, URLs, raw tool output
    source_tool = Column(String(100))
    source_url = Column(String(500))

    # Timing
    detected_at = Column(DateTime(timezone=True), server_default=func.now())  # when qlGen discovered it
    evidence_date = Column(DateTime(timezone=True))  # when the real-world event actually occurred
    expires_at = Column(DateTime(timezone=True))  # computed from signal type half-life

    # Lifecycle
    is_archived = Column(Boolean, default=False)
    is_dismissed = Column(Boolean, default=False)
    is_saved = Column(Boolean, default=False)
    is_snoozed = Column(Boolean, default=False)
    snoozed_until = Column(DateTime(timezone=True))
    saved_at = Column(DateTime(timezone=True))
    snoozed_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_signal_company_created", "company_kb_id", "created_at"),
        Index("ix_signal_type", "signal_type"),
        Index("ix_signal_priority", "priority"),
        Index("ix_signal_expires", "expires_at"),
        Index("ix_signal_archived", "is_archived"),
        Index("ix_signal_saved", "is_saved"),
        Index("ix_signal_snoozed", "is_snoozed", "snoozed_until"),
    )
