import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base


class PipelineLog(Base):
    __tablename__ = "pipeline_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_run_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    event_data = Column(JSONB, nullable=False)
    sequence_number = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    pipeline_run = relationship("PipelineRun", back_populates="logs")
