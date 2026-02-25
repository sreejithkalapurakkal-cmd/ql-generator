from pydantic import BaseModel, Field


class BANTScore(BaseModel):
    budget: float = Field(ge=0, le=10)
    authority: float = Field(ge=0, le=10)
    need: float = Field(ge=0, le=10)
    timeline: float = Field(ge=0, le=10)
    total: float = Field(ge=0, le=10)
    reasoning: str = ""


class Lead(BaseModel):
    company_name: str = Field(alias="companyName", default="")
    domain: str = ""
    industry: str = ""
    employee_count: int | None = Field(alias="employeeCount", default=None)
    estimated_revenue: int | None = Field(alias="estimatedRevenue", default=None)
    location: str | None = None
    description: str | None = None
    tech_stack: list[str] = Field(alias="techStack", default_factory=list)
    funding_stage: str | None = Field(alias="fundingStage", default=None)
    bant_score: BANTScore = Field(alias="bantScore")

    model_config = {"populate_by_name": True}
