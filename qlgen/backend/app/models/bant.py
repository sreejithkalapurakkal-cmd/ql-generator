import uuid
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base


class BANTScore(Base):
    __tablename__ = "bant_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    contact_id = Column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True)
    budget_score = Column(Integer)
    budget_reason = Column(Text)
    budget_sources = Column(JSONB)
    authority_score = Column(Integer)
    authority_reason = Column(Text)
    authority_sources = Column(JSONB)
    need_score = Column(Integer)
    need_reason = Column(Text)
    need_sources = Column(JSONB)
    timing_score = Column(Integer)
    timing_reason = Column(Text)
    timing_sources = Column(JSONB)
    total_score = Column(Integer)
    overall_summary = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company", back_populates="bant_score",
                           foreign_keys=[company_id])
