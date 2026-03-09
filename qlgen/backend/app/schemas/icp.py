from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class ICPGenerateRequest(BaseModel):
    description: str


class ICPGenerateResponse(BaseModel):
    name: str
    description: Optional[str] = None
    config: dict


class ICPConfigCreate(BaseModel):
    name: str
    description: Optional[str] = None
    config: dict


class ICPConfigUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[dict] = None


class ICPConfigResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    config: dict
    created_at: datetime
    updated_at: Optional[datetime]
    is_active: bool

    class Config:
        from_attributes = True
