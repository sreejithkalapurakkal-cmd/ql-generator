from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Any


class ContactResponse(BaseModel):
    id: UUID
    full_name: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    designation: Optional[str]
    role_category: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    linkedin_url: Optional[str]
    city: Optional[str]
    source: Optional[str]
    confidence: Optional[float]
    enrichment_status: Optional[str]

    class Config:
        from_attributes = True


class CompanyStageResultResponse(BaseModel):
    id: UUID
    stage: str
    status: str
    score: Optional[float] = None
    reasoning: Optional[str] = None
    evidence: Optional[Any] = None
    user_override: Optional[bool] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CompanyResponse(BaseModel):
    id: UUID
    name: str
    website: Optional[str]
    industry: Optional[str]
    sub_industry: Optional[str]
    city: Optional[str]
    state_region: Optional[str]
    country: Optional[str]
    employee_count: Optional[int]
    revenue_estimate: Optional[int]
    asset_value: Optional[int] = None
    tech_stack_json: Optional[Any] = None
    source: Optional[str]
    qualification: Optional[str]
    icp_match_score: Optional[float]
    match_reasoning: Optional[str]
    contacts: List[ContactResponse] = []
    promoted: Optional[bool] = None
    description: Optional[str] = None
    raw_data_json: Optional[Any] = None
    rejection_reason: Optional[str] = None
    disqualification_stage: Optional[str] = None
    created_at: datetime

    # v2 pipeline fields
    current_stage: Optional[str] = None
    budget_signal_score: Optional[float] = None
    urgency_signal_score: Optional[float] = None
    final_score: Optional[float] = None
    final_rank: Optional[int] = None
    cached_from_run_id: Optional[UUID] = None
    data_freshness: Optional[datetime] = None
    stage_results: List[CompanyStageResultResponse] = []

    carried_forward: Optional[bool] = None

    # Recency-adjusted scoring
    recency_adjusted_budget_score: Optional[float] = None
    recency_adjusted_urgency_score: Optional[float] = None
    deal_hotness_score: Optional[float] = None
    deal_hotness_tier: Optional[str] = None
    avg_evidence_age_months: Optional[float] = None

    # LinkedIn / Evaboot enrichment fields
    domain: Optional[str] = None
    linkedin_url: Optional[str] = None
    company_type: Optional[str] = None
    year_founded: Optional[int] = None
    revenue_min: Optional[int] = None
    revenue_max: Optional[int] = None
    employee_growth_1y_pct: Optional[float] = None
    funding_stage: Optional[str] = None
    discovery_method: Optional[str] = None
    headquarters_address: Optional[str] = None
    linkedin_data: Optional[Any] = None

    # Cross-run context (populated by /all/companies endpoint)
    pipeline_run_id: Optional[UUID] = None
    run_icp_name: Optional[str] = None

    class Config:
        from_attributes = True


class LeadExportRow(BaseModel):
    serial: int
    company_name: str
    website: Optional[str]
    geo_city: Optional[str]
    contact_name: Optional[str]
    designation: Optional[str]
    linkedin: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    final_score: Optional[float]
    budget_signal_score: Optional[float] = None
    urgency_signal_score: Optional[float] = None
    deal_hotness_score: Optional[float] = None
    deal_hotness_tier: Optional[str] = None
