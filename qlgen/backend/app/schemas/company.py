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


class BANTScoreResponse(BaseModel):
    id: UUID
    budget_score: Optional[int]
    budget_reason: Optional[str]
    authority_score: Optional[int]
    authority_reason: Optional[str]
    need_score: Optional[int]
    need_reason: Optional[str]
    timing_score: Optional[int]
    timing_reason: Optional[str]
    total_score: Optional[int]
    overall_summary: Optional[str]

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
    tech_stack_json: Optional[Any] = None
    source: Optional[str]
    qualification: Optional[str]
    icp_match_score: Optional[float]
    match_reasoning: Optional[str]
    contacts: List[ContactResponse] = []
    bant_score: Optional[BANTScoreResponse] = None
    created_at: datetime

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
    bant_score: Optional[int]
