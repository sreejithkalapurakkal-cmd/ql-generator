"""Reusable RBAC helpers for data isolation.

Normal users see only their own data. Super admins see everything
(including legacy records with NULL user_id).
"""
from fastapi import HTTPException
from sqlalchemy import true

from app.models.user import User


def is_admin(user: User) -> bool:
    """Check if the user has super_admin role."""
    return user.role == "super_admin"


def ownership_filter(user_id_column, user: User):
    """Return a SQLAlchemy WHERE clause for data isolation.

    Admin: no-op (returns all rows).
    Normal user: filters to rows owned by the user.
    """
    if is_admin(user):
        return true()
    return user_id_column == user.id


def check_resource_access(resource_user_id, user: User) -> None:
    """Raise 404 if user doesn't own the resource and isn't admin.

    Returns 404 (not 403) to avoid leaking resource existence.
    """
    if is_admin(user):
        return
    if resource_user_id is None or resource_user_id != user.id:
        raise HTTPException(status_code=404, detail="Resource not found")


def check_edit_permission(resource_user_id, user: User) -> None:
    """Raise 403 if user is admin but not the owner.

    Admins can view and delete but cannot edit another user's resources.
    """
    if resource_user_id is not None and resource_user_id != user.id:
        if is_admin(user):
            raise HTTPException(status_code=403, detail="Cannot edit another user's resource")
        raise HTTPException(status_code=404, detail="Resource not found")


def check_delete_permission(resource_user_id, user: User) -> None:
    """Allow owner OR admin to delete. Raise 404 for non-owner non-admins."""
    if is_admin(user):
        return
    if resource_user_id is None or resource_user_id != user.id:
        raise HTTPException(status_code=404, detail="Resource not found")
