from pydantic import BaseModel, Field


class ProgressUpdate(BaseModel):
    job_id: str = Field(alias="jobId", serialization_alias="jobId")
    stage: str
    message: str
    progress: int

    model_config = {"populate_by_name": True}
