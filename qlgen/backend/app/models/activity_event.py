import uuid
from sqlalchemy import Column, String, Text, Float, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db.base import Base


class ActivityEvent(Base):
    """Human-friendly research activity narration.

    Each event records a step in a research job with both a user-friendly
    narrative and optional technical detail for debugging. Events are
    categorized by type and can be flagged as milestones for summary views.

    Event types: research_start, tool_call, signal_detected,
    section_generated, correlation_found, verification_complete,
    contact_found, brief_ready, research_complete, error.

    Categories: research, signal, synthesis, contact, outreach.
    """
    __tablename__ = "activity_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_job_id = Column(UUID(as_uuid=True), nullable=True)
    company_kb_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_knowledge_base.id", ondelete="CASCADE"),
        nullable=True,
    )
    event_type = Column(String(50), nullable=False)
    event_category = Column(String(50))  # research, signal, synthesis, contact, outreach
    narrative = Column(Text, nullable=False)  # Human-friendly description
    narrative_detail = Column(Text)  # Expanded explanation
    technical_detail = Column(JSONB)  # Tool call data, timing, etc.
    confidence = Column(Float)
    milestone = Column(Boolean, default=False)
    verbosity_level = Column(String(20), default="summary")  # summary, detailed, technical
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_activity_job", "research_job_id", "created_at"),
        Index("ix_activity_company", "company_kb_id", "created_at"),
    )
