import uuid
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db.base import Base


class ResearchJob(Base):
    """Tracks a multi-stage research job for a company.

    Job types: full_research, signal_scan, contact_enrichment, brief_generation
    Status: pending → running → completed | failed | cancelled
    """
    __tablename__ = "research_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_kb_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_knowledge_base.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    job_type = Column(String(50), nullable=False)  # full_research, signal_scan, contact_enrichment, brief_generation
    status = Column(String(20), default="pending")  # pending, running, completed, failed, cancelled
    research_depth = Column(String(20), default="standard")  # standard, deep, comprehensive

    # Configuration
    config = Column(JSONB, default=dict)  # signal_types, custom_hints, etc.
    plan = Column(JSONB)  # Research Planner Agent output

    # Progress tracking
    progress = Column(JSONB, default=dict)  # {current_stage, stages_completed, percent, label}
    current_stage = Column(String(100))

    # Results
    results = Column(JSONB)  # Aggregated specialist agent outputs
    signals_detected = Column(Integer, default=0)
    contacts_found = Column(Integer, default=0)
    brief_version = Column(Integer)

    # Cost tracking
    total_tool_calls = Column(Integer, default=0)
    total_cost_usd = Column(Float, default=0.0)

    # Timing
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    error = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_research_job_company", "company_kb_id", "created_at"),
        Index("ix_research_job_status", "status"),
        Index("ix_research_job_user", "user_id"),
    )
