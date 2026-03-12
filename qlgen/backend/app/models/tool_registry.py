import uuid
from sqlalchemy import Column, String, Boolean, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base import Base


class ToolRegistry(Base):
    __tablename__ = "tool_registry"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tool_name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False)  # pipeline | research | copilot_db
    requires_api_key = Column(Boolean, default=False)
    api_key_env_var = Column(String(100), nullable=True)
    base_url = Column(String(500), nullable=True)
    is_enabled = Column(Boolean, default=True)
    health_status = Column(String(50), default="unknown")  # healthy | unhealthy | no_api_key | unknown
    last_health_check_at = Column(DateTime(timezone=True), nullable=True)
    last_health_message = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    rate_limit_info = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
