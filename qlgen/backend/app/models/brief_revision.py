import uuid
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db.base import Base


class BriefRevision(Base):
    """Versioned research brief for a company.

    Each revision contains structured sections (overview, org, signals,
    competitive, tech, budget, why-now, angle) with inline citations,
    bullet points, and source attribution. Briefs are append-only:
    new versions are created, never modified.

    Sections schema (JSONB):
    [
        {
            "id": "overview",
            "heading": "Company Overview",
            "body": "Text with inline [1] citations...",
            "bullets": ["bullet 1", "bullet 2"],
            "sources": [
                {"label": "...", "source_class": "SEC filing", "url": "...", "date": "..."}
            ],
            "insufficient": false,
            "confidence": 0.85
        },
        ...
    ]
    """
    __tablename__ = "brief_revisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_kb_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_knowledge_base.id", ondelete="CASCADE"),
        nullable=False,
    )
    version = Column(Integer, nullable=False)
    sections = Column(JSONB, nullable=False)
    word_count = Column(Integer)
    generated_by = Column(String(20), default="auto")  # auto, manual
    trigger_signal_id = Column(
        UUID(as_uuid=True),
        ForeignKey("signal_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    trigger_signal_headline = Column(String(500))
    model_id = Column(String(100))
    generation_cost_usd = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_brief_company", "company_kb_id", "version"),
        UniqueConstraint("company_kb_id", "version", name="uq_brief_company_version"),
    )
