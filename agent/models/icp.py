from pydantic import BaseModel, Field


class ICPProfile(BaseModel):
    industries: list[str]
    company_size_range: dict = Field(alias="companySizeRange", default_factory=dict)
    revenue_range: dict = Field(alias="revenueRange", default_factory=dict)
    geographies: list[str] = []
    tech_stack: list[str] = Field(alias="techStack", default_factory=list)
    keywords: list[str] = []
    additional_notes: str = Field(alias="additionalNotes", default="")

    model_config = {"populate_by_name": True}


class BANTWeights(BaseModel):
    budget: float = Field(ge=0, le=1)
    authority: float = Field(ge=0, le=1)
    need: float = Field(ge=0, le=1)
    timeline: float = Field(ge=0, le=1)
