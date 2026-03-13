from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional


class GoogleCallbackRequest(BaseModel):
    code: str
    redirect_uri: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: Optional[str]
    picture_url: Optional[str]
    role: str
    is_active: bool
    created_at: Optional[datetime]
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserInviteRequest(BaseModel):
    email: str
    role: str = "user"


class UserUpdateRequest(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    name: Optional[str] = None
