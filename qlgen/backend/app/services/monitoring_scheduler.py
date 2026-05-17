"""Scheduled Monitoring Service.

Checks tracking lists for overdue monitoring and triggers signal detection.
Designed to be called by a cron endpoint (CloudWatch Events, external scheduler,
or manual trigger).

The monitoring_config on TrackingList controls:
  {
    "enabled": true,
    "frequency_days": 7,       # how often to scan
    "signal_types": [...],     # optional signal type filter
    "alert_threshold": "high"  # minimum priority to notify
  }
"""
import asyncio
import logging
import uuid as uuid_mod
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.models.tracking_list import TrackingList
from app.models.signal_detection_run import SignalDetectionRun
from app.services.signal_detection_runner import execute_signal_detection

logger = logging.getLogger(__name__)


async def check_and_trigger_monitoring(
    db: AsyncSession | None = None,
    dry_run: bool = False,
) -> dict:
    """Check all tracking lists for overdue monitoring and trigger signal detection.

    Args:
        db: Optional session (creates own if not provided).
        dry_run: If True, returns what would be triggered without actually running.

    Returns:
        Summary dict: {triggered: int, skipped: int, lists: [...]}
    """
    own_session = db is None
    if own_session:
        session_ctx = async_session()
        db = await session_ctx.__aenter__()
    else:
        session_ctx = None

    try:
        now = datetime.now(timezone.utc)

        # Find lists that are due for monitoring
        result = await db.execute(
            select(TrackingList).where(
                TrackingList.is_active == True,
            )
        )
        all_lists = list(result.scalars().all())

        triggered = []
        skipped = []

        for tracking_list in all_lists:
            config = tracking_list.monitoring_config or {}
            if not config.get("enabled", False):
                skipped.append({
                    "list_id": str(tracking_list.id),
                    "name": tracking_list.name,
                    "reason": "monitoring_disabled",
                })
                continue

            frequency_days = config.get("frequency_days", 7)

            # Check if monitoring is due
            if tracking_list.next_monitor_due and tracking_list.next_monitor_due > now:
                skipped.append({
                    "list_id": str(tracking_list.id),
                    "name": tracking_list.name,
                    "reason": "not_due",
                    "next_due": tracking_list.next_monitor_due.isoformat(),
                })
                continue

            # Check if list has companies
            if (tracking_list.company_count or 0) == 0:
                skipped.append({
                    "list_id": str(tracking_list.id),
                    "name": tracking_list.name,
                    "reason": "no_companies",
                })
                continue

            if dry_run:
                triggered.append({
                    "list_id": str(tracking_list.id),
                    "name": tracking_list.name,
                    "user_id": str(tracking_list.user_id),
                    "company_count": tracking_list.company_count,
                    "dry_run": True,
                })
                continue

            # Create a signal detection run
            run = SignalDetectionRun(
                id=uuid_mod.uuid4(),
                tracking_list_id=tracking_list.id,
                user_id=tracking_list.user_id,
                status="pending",
                total_companies=tracking_list.company_count or 0,
            )
            db.add(run)

            # Update monitoring timestamps
            tracking_list.last_monitored_at = now
            tracking_list.next_monitor_due = now + timedelta(days=frequency_days)

            await db.flush()

            triggered.append({
                "list_id": str(tracking_list.id),
                "name": tracking_list.name,
                "user_id": str(tracking_list.user_id),
                "run_id": str(run.id),
                "company_count": tracking_list.company_count,
            })

            # Launch the detection task
            asyncio.create_task(execute_signal_detection(run.id))

        await db.commit()

        return {
            "triggered": len(triggered),
            "skipped": len(skipped),
            "lists_triggered": triggered,
            "lists_skipped": skipped,
            "checked_at": now.isoformat(),
        }

    except Exception as e:
        logger.error(f"Monitoring scheduler failed: {e}", exc_info=True)
        return {"error": str(e), "triggered": 0, "skipped": 0}

    finally:
        if own_session and session_ctx:
            await session_ctx.__aexit__(None, None, None)


async def configure_monitoring(
    db: AsyncSession,
    tracking_list_id,
    enabled: bool,
    frequency_days: int = 7,
    signal_types: list[str] | None = None,
    alert_threshold: str = "high",
) -> dict:
    """Configure monitoring for a tracking list."""
    from uuid import UUID
    result = await db.execute(
        select(TrackingList).where(TrackingList.id == tracking_list_id)
    )
    tracking_list = result.scalar_one_or_none()
    if not tracking_list:
        return {"error": "Tracking list not found"}

    config = {
        "enabled": enabled,
        "frequency_days": max(1, min(frequency_days, 30)),
        "signal_types": signal_types or [],
        "alert_threshold": alert_threshold,
    }
    tracking_list.monitoring_config = config

    if enabled and not tracking_list.next_monitor_due:
        tracking_list.next_monitor_due = (
            datetime.now(timezone.utc) + timedelta(days=frequency_days)
        )

    await db.flush()

    return {
        "list_id": str(tracking_list.id),
        "monitoring_config": config,
        "next_monitor_due": tracking_list.next_monitor_due.isoformat() if tracking_list.next_monitor_due else None,
    }
