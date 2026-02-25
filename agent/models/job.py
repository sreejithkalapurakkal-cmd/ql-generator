from pydantic import BaseModel, Field

from .icp import ICPProfile, BANTWeights
from .lead import Lead


class JobRequest(BaseModel):
    job_id: str = Field(alias="jobId")
    icp_profile: ICPProfile = Field(alias="icpProfile")
    bant_weights: BANTWeights = Field(alias="bantWeights")
    max_results: int = Field(alias="maxResults", default=25)
    callback_url: str = Field(alias="callbackUrl")

    model_config = {"populate_by_name": True}


class JobCallback(BaseModel):
    job_id: str = Field(alias="jobId", serialization_alias="jobId")
    status: str
    leads: list[Lead] = []
    error: str | None = None

    model_config = {"populate_by_name": True}
