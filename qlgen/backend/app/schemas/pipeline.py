from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List


class PipelineOptions(BaseModel):
    max_contacts_per_company: int = 5


class PipelineRunRequest(BaseModel):
    icp_config_id: UUID
    options: PipelineOptions = PipelineOptions()
    discovery_mode: str = "qlgen_only"  # qlgen_only | sales_navigator_only | sales_navigator_plus_qlgen
    sales_navigator_url: Optional[str] = None
    expected_result_count: Optional[int] = None


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
    signal_mode: Optional[str] = None
    signal_phase: Optional[str] = None
    stage_details: Optional[dict] = None
    user_name: Optional[str] = None
    discovery_mode: Optional[str] = None
    sales_navigator_url: Optional[str] = None
    evaboot_credits_used: Optional[int] = None
    expected_result_count: Optional[int] = None

    class Config:
        from_attributes = True


class PromoteFirmographicRequest(BaseModel):
    company_ids: List[UUID]
    signal_mode: str = "both"  # budget_first | urgency_first | both


class PromoteFirstSignalRequest(BaseModel):
    """Used in serial mode after reviewing the first signal type."""
    company_ids: List[UUID]


class PromoteSignalsRequest(BaseModel):
    """Used after the final signal review (all modes)."""
    company_ids: List[UUID]


class PipelineLogResponse(BaseModel):
    id: UUID
    event_type: str
    event_data: dict
    sequence_number: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
