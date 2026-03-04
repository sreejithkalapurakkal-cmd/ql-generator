from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class PipelineOptions(BaseModel):
    max_companies: int = 25
    max_contacts_per_company: int = 5


class PipelineRunRequest(BaseModel):
    icp_config_id: UUID
    options: PipelineOptions = PipelineOptions()


class PipelineRunResponse(BaseModel):
    id: UUID
    icp_config_id: UUID
    icp_name: Optional[str] = None
    icp_description: Optional[str] = None
    icp_config: Optional[dict] = None
    status: str
    current_stage: Optional[str]
    companies_found: int
    contacts_found: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_log: Optional[str] = None
    estimated_duration_seconds: Optional[int] = None

    class Config:
        from_attributes = True


class PipelineLogResponse(BaseModel):
    id: UUID
    event_type: str
    event_data: dict
    sequence_number: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
