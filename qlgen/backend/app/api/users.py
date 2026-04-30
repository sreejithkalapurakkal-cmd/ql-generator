import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.auth.dependencies import get_current_user, get_current_super_admin
from app.schemas.auth import UserResponse, UserInviteRequest, UserUpdateRequest, CreditQuotaResponse
from app.services.audit_service import log_audit
from app.services.credit_service import get_credit_usage_today

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/users", tags=["User Management"])


@router.get("", response_model=list[UserResponse])
async def list_users(
    _admin: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all users (super_admin only)."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def invite_user(
    request: UserInviteRequest,
    http_request: Request,
    admin: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Invite a new user by email (super_admin only)."""
    email = request.email.lower().strip()

    # Validate domain
    if settings.ALLOWED_EMAIL_DOMAIN:
        domain = email.split("@")[-1] if "@" in email else ""
        if domain != settings.ALLOWED_EMAIL_DOMAIN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only @{settings.ALLOWED_EMAIL_DOMAIN} emails are allowed",
            )

    # Validate role
    if request.role not in ("user", "admin", "super_admin"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role must be 'user', 'admin', or 'super_admin'")

    # Check for existing user
    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")

    user = User(email=email, role=request.role, is_active=True)
    db.add(user)
    await db.flush()
    await log_audit(db, admin.id, "create", "user", user.id, {"email": email, "role": request.role}, ip_address=http_request.client.host if http_request.client else None)
    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.get("/me/credit-quota", response_model=CreditQuotaResponse)
async def get_my_credit_quota(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's daily credit quota status."""
    usage = await get_credit_usage_today(user.id, db)
    daily_limit = user.daily_credit_limit
    remaining = None
    if daily_limit is not None:
        remaining = max(0, daily_limit - usage["used_today"] - usage["reserved"])
    return CreditQuotaResponse(
        daily_limit=daily_limit,
        used_today=usage["used_today"],
        remaining=remaining,
        runs_in_progress=usage["runs_in_progress"],
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    request: UserUpdateRequest,
    http_request: Request,
    admin: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a user's role, active status, or name (super_admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    changed_fields = []
    if request.role is not None:
        if request.role not in ("user", "admin", "super_admin"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role must be 'user', 'admin', or 'super_admin'")
        user.role = request.role
        changed_fields.append("role")
    if request.is_active is not None:
        user.is_active = request.is_active
        changed_fields.append("is_active")
    if request.name is not None:
        user.name = request.name
        changed_fields.append("name")
    if request.daily_credit_limit is not None:
        # -1 is sentinel for "set to unlimited (None)"
        user.daily_credit_limit = None if request.daily_credit_limit == -1 else request.daily_credit_limit
        changed_fields.append("daily_credit_limit")

    await log_audit(db, admin.id, "update", "user", user.id, {"changed_fields": changed_fields, "email": user.email}, ip_address=http_request.client.host if http_request.client else None)
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    http_request: Request,
    admin: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a user (super_admin only). Cannot delete yourself."""
    if admin.id == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await log_audit(db, admin.id, "delete", "user", user.id, {"email": user.email}, ip_address=http_request.client.host if http_request.client else None)
    await db.delete(user)
    await db.commit()
    return {"message": "User deleted"}
