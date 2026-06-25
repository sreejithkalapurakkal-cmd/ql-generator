"""User settings API endpoints."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

# Default settings applied when a user has no saved preferences
DEFAULT_SETTINGS = {
    "notifications": {
        "signal_detected": True,
        "brief_generated": True,
        "contact_enriched": True,
        "monitoring_complete": True,
    },
    "monitoring_defaults": {
        "frequency_days": 7,
        "signal_types": [],
        "alert_threshold": "high",
    },
    "outreach_defaults": {
        "voice_profile": "concise",
        "tone": "direct",
        "format": "email",
    },
    "display": {
        "signal_feed_show_low_confidence": False,
        "activity_feed_verbosity": "summary",
    },
}


class SettingsUpdate(BaseModel):
    notifications: Optional[dict] = None
    monitoring_defaults: Optional[dict] = None
    outreach_defaults: Optional[dict] = None
    display: Optional[dict] = None


@router.get("")
async def get_settings(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get current user's settings with defaults applied."""
    user_settings = user.settings or {}

    # Deep merge: user settings override defaults
    merged = {}
    for key, default_value in DEFAULT_SETTINGS.items():
        if isinstance(default_value, dict):
            merged[key] = {**default_value, **(user_settings.get(key) or {})}
        else:
            merged[key] = user_settings.get(key, default_value)

    return {
        "settings": merged,
        "user_id": str(user.id),
    }


@router.patch("")
async def update_settings(
    request: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update current user's settings. Partial updates are merged."""
    current = user.settings or {}

    # Merge each section
    update_data = request.model_dump(exclude_none=True)
    for key, value in update_data.items():
        if isinstance(value, dict) and isinstance(current.get(key), dict):
            current[key] = {**current[key], **value}
        else:
            current[key] = value

    user.settings = current
    await db.commit()

    # Return merged with defaults
    merged = {}
    for key, default_value in DEFAULT_SETTINGS.items():
        if isinstance(default_value, dict):
            merged[key] = {**default_value, **(current.get(key) or {})}
        else:
            merged[key] = current.get(key, default_value)

    return {
        "settings": merged,
        "user_id": str(user.id),
    }
