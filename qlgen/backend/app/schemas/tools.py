from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class ToolRegistryResponse(BaseModel):
    id: UUID
    tool_name: str
    display_name: str
    category: str
    requires_api_key: bool
    api_key_env_var: Optional[str] = None
    base_url: Optional[str] = None
    is_enabled: bool
    health_status: str
    last_health_check_at: Optional[datetime] = None
    last_health_message: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Computed metrics from pipeline_logs
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    success_rate: Optional[float] = None
    last_used_at: Optional[datetime] = None
    last_error: Optional[str] = None

    class Config:
        from_attributes = True


class ToolRegistryUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    notes: Optional[str] = None


class ToolHealthCheckResponse(BaseModel):
    tool_name: str
    status: str
    message: str
    checked_at: datetime


class ToolMetricsSummary(BaseModel):
    total_tools: int = 0
    healthy_count: int = 0
    unhealthy_count: int = 0
    disabled_count: int = 0
    no_api_key_count: int = 0
    unknown_count: int = 0
