from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class PageContext(BaseModel):
    route: Optional[str] = None
    page_type: Optional[str] = None
    run_id: Optional[str] = None
    company_id: Optional[str] = None
    icp_id: Optional[str] = None


class ChatMessageRequest(BaseModel):
    session_id: Optional[UUID] = None
    message: str
    page_context: Optional[PageContext] = None


class ChatMessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    tool_calls: Optional[list] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChatSessionResponse(BaseModel):
    id: UUID
    title: Optional[str] = None
    page_context: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    message_count: int = 0
    last_message_preview: Optional[str] = None

    class Config:
        from_attributes = True


class RecommendationItem(BaseModel):
    icon: str
    text: str
    prompt: str


class RecommendationsRequest(BaseModel):
    page_context: Optional[PageContext] = None


class RecommendationsResponse(BaseModel):
    recommendations: list[RecommendationItem]
