import uuid
from sqlalchemy import Column, String, Text, Integer, BigInteger, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.db.base import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_run_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id"))
    name = Column(String(500), nullable=False)
    website = Column(String(500))
    industry = Column(String(255))
    sub_industry = Column(String(255))
    city = Column(String(255))
    state_region = Column(String(255))
    country = Column(String(255))
    employee_count = Column(Integer)
    revenue_estimate = Column(BigInteger)
    tech_stack_json = Column(JSONB)
    description = Column(Text)
    source = Column(String(100))
    source_id = Column(String(500))
    qualification = Column(String(50), default="qualified")
    rejection_reason = Column(Text)
    icp_match_score = Column(Float)
    match_reasoning = Column(Text)
    raw_data_json = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    contacts = relationship("Contact", back_populates="company", cascade="all, delete-orphan")
    bant_score = relationship("BANTScore", back_populates="company", uselist=False,
                              primaryjoin="and_(Company.id==BANTScore.company_id, BANTScore.contact_id==None)",
                              cascade="all, delete-orphan")
    pipeline_run = relationship("PipelineRun", back_populates="companies")
