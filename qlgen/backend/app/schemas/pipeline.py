from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List


class BANTWeights(BaseModel):
    budget: int = Field(default=3, ge=1, le=5)
    authority: int = Field(default=3, ge=1, le=5)
    need: int = Field(default=3, ge=1, le=5)
    timing: int = Field(default=3, ge=1, le=5)


class PipelineOptions(BaseModel):
    max_companies: int = 25
    max_contacts_per_company: int = 5
    pipeline_mode: str = "single_run"
    match_strictness: str = "moderate"
    bant_weights: BANTWeights = BANTWeights()


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
    pipeline_mode: Optional[str] = None
    match_strictness: Optional[str] = None
    bant_weights: Optional[dict] = None
    stage_details: Optional[dict] = None

    class Config:
        from_attributes = True


class PromoteCompaniesRequest(BaseModel):
    company_ids: List[UUID]


class PipelineLogResponse(BaseModel):
    id: UUID
    event_type: str
    event_data: dict
    sequence_number: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
