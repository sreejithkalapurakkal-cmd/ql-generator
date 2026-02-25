import uuid
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    icp_config_id = Column(UUID(as_uuid=True), ForeignKey("icp_configs.id"))
    status = Column(String(50), default="pending")
    current_stage = Column(String(100))
    companies_found = Column(Integer, default=0)
    contacts_found = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    error_log = Column(Text)
    stage_details = Column(JSONB)
    options = Column(JSONB)

    icp_config = relationship("ICPConfig", back_populates="pipeline_runs")
    companies = relationship("Company", back_populates="pipeline_run", cascade="all, delete-orphan")
