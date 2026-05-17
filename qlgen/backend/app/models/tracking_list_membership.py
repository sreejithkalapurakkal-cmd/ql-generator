import uuid
from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base


class TrackingListMembership(Base):
    """Junction between TrackingList and CompanyKnowledgeBase.

    Each row represents one company tracked in one list, with outreach
    state, signal heat score, and user annotations.

    Critical: references CompanyKnowledgeBase.id (golden record),
    NOT per-run Company.id. This is separate from Company.promoted
    (pipeline-internal review gate).
    """
    __tablename__ = "tracking_list_memberships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tracking_list_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tracking_lists.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_kb_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_knowledge_base.id", ondelete="CASCADE"),
        nullable=False,
    )

    # How this company was added
    added_from = Column(String(50), nullable=False)  # upload, kb_browser, pipeline, manual

    # User annotations
    notes = Column(Text)

    # Outreach pipeline
    outreach_status = Column(String(50), default="not_started")
    # not_started, drafted, sent, replied, meeting_booked, won, lost
    outreach_history = Column(JSONB, default=list)  # [{status, timestamp, note}]

    # Materialized composite signal score (recomputed on signal changes + daily decay)
    signal_heat_score = Column(Float, default=0.0)

    # Tags as JSONB array of tag UUIDs (GIN indexed for fast filtering)
    tags = Column(JSONB, default=list)

    # Contact enrichment status: not_started, in_progress, enriched, failed
    enrichment_status = Column(String(50), default="not_started")

    # Snooze: hide from active views until this date
    snoozed_until = Column(DateTime(timezone=True))

    added_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tracking_list = relationship("TrackingList", back_populates="memberships")
    company_kb = relationship("CompanyKnowledgeBase", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("tracking_list_id", "company_kb_id", name="uq_list_company"),
        Index("ix_membership_list_id", "tracking_list_id"),
        Index("ix_membership_kb_id", "company_kb_id"),
        Index("ix_membership_outreach", "outreach_status"),
        Index("ix_membership_heat", "signal_heat_score"),
        Index(
            "ix_membership_tags_gin",
            "tags",
            postgresql_using="gin",
        ),
    )
