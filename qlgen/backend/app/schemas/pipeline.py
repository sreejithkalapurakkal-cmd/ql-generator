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
    status: str
    current_stage: Optional[str]
    companies_found: int
    contacts_found: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_log: Optional[str] = None

    class Config:
        from_attributes = True
