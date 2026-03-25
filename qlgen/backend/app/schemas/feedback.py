from pydantic import BaseModel, field_validator
from uuid import UUID
from datetime import datetime
from typing import Optional


VALID_TYPES = {"feedback", "complaint", "bug_report", "feature_request"}
VALID_STATUSES = {"open", "in_progress", "resolved", "closed"}


class FeedbackCreate(BaseModel):
    type: str
    subject: str
    description: str

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_TYPES:
            raise ValueError(f"type must be one of: {', '.join(sorted(VALID_TYPES))}")
        return v


class FeedbackStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(VALID_STATUSES))}")
        return v


class FeedbackReplyCreate(BaseModel):
    message: str


class FeedbackReplyResponse(BaseModel):
    id: UUID
    feedback_id: UUID
    user_id: UUID
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    message: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FeedbackResponse(BaseModel):
    id: UUID
    user_id: UUID
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    type: str
    subject: str
    description: str
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    replies: list[FeedbackReplyResponse] = []

    class Config:
        from_attributes = True


class FeedbackListResponse(BaseModel):
    id: UUID
    user_id: UUID
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    type: str
    subject: str
    status: str
    reply_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
