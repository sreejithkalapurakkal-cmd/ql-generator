import uuid
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db.base import Base


class CustomSignalSource(Base):
    """User-defined signal source for monitoring.

    Source types: website, careers, blog, press, sec, linkedin, github, rss
    Crawl frequency: daily, weekly, biweekly, monthly
    """
    __tablename__ = "custom_signal_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    company_kb_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_knowledge_base.id", ondelete="CASCADE"),
        nullable=True,
    )
    source_type = Column(String(50), nullable=False)
    url = Column(String(1000), nullable=False)
    name = Column(String(255))
    crawl_frequency = Column(String(20), default="weekly")
    last_crawled_at = Column(DateTime(timezone=True))
    last_content_hash = Column(String(64))
    reliability_score = Column(Float, default=0.5)
    freshness_score = Column(Float, default=1.0)
    enabled = Column(Boolean, default=True)
    crawl_config = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_source_user", "user_id"),
        Index("ix_source_company", "company_kb_id"),
    )


class SourceSnapshot(Base):
    """Point-in-time snapshot of a crawled source for change detection."""
    __tablename__ = "source_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("custom_signal_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    content_hash = Column(String(64), nullable=False)
    content_summary = Column(String(2000))
    extracted_signals = Column(JSONB, default=list)
    crawled_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_snapshot_source", "source_id", "crawled_at"),
    )
