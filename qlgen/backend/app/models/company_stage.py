import uuid
from sqlalchemy import Column, String, Text, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base


class CompanyStageResult(Base):
    __tablename__ = "company_stage_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    stage = Column(String(50), nullable=False)       # industry_discovery, firmographic_fit, budget_signals, urgency_signals, contact_discovery
    status = Column(String(50), nullable=False)       # passed, failed, skipped, promoted, excluded
    score = Column(Float, nullable=True)              # stage-specific score (0-100)
    reasoning = Column(Text, nullable=True)           # why included/excluded at this stage
    evidence = Column(JSONB, nullable=True)           # [{signal, description, source_url, tool, confidence}]
    user_override = Column(Boolean, nullable=True)    # True=user included, False=user excluded, null=no override
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company", back_populates="stage_results")
