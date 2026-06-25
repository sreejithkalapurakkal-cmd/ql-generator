"""Scheduled Monitoring Service.

Checks tracking lists for overdue monitoring and triggers signal detection.
Called automatically by the in-process APScheduler (scheduler_service.py),
or manually via POST /api/v1/signals/monitoring/check.

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
import random
import uuid as uuid_mod
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import async_session
from app.models.tracking_list import TrackingList
from app.models.signal_detection_run import SignalDetectionRun
from app.services.signal_detection_runner import execute_signal_detection

logger = logging.getLogger(__name__)

# Signal types ordered by half-life (fastest decay first) for priority sorting
_FAST_DECAY_TYPES = {"funding", "earnings_report", "product_launch", "competitor_churn", "press_mention"}


def _sort_key_for_list(tracking_list: TrackingList, now: datetime) -> tuple:
    """Sort overdue lists: fast-decay signal types first, then longest overdue."""
    config = tracking_list.monitoring_config or {}
    signal_types = set(config.get("signal_types") or [])

    # Priority: lists tracking fast-decay signals get lower (higher priority) sort key
    has_fast_decay = 0 if signal_types & _FAST_DECAY_TYPES else 1

    # Longer overdue = higher priority (more negative = sorted first)
    overdue_seconds = 0
    if tracking_list.next_monitor_due:
        overdue_seconds = -(now - tracking_list.next_monitor_due).total_seconds()

    return (has_fast_decay, overdue_seconds)


async def check_and_trigger_monitoring(
    db: AsyncSession | None = None,
    dry_run: bool = False,
) -> dict:
    """Check all tracking lists for overdue monitoring and trigger signal detection.

    Respects concurrency limits (MONITORING_MAX_CONCURRENT_LISTS) and staggers
    launches (MONITORING_STAGGER_SECONDS) to avoid API rate-limit storms.

    Args:
        db: Optional session (creates own if not provided).
        dry_run: If True, returns what would be triggered without actually running.

    Returns:
        Summary dict: {triggered: int, skipped: int, deferred: int, lists: [...]}
    """
    own_session = db is None
    if own_session:
        session_ctx = async_session()
        db = await session_ctx.__aenter__()
    else:
        session_ctx = None

    settings = get_settings()
    max_concurrent = settings.MONITORING_MAX_CONCURRENT_LISTS
    stagger_seconds = settings.MONITORING_STAGGER_SECONDS

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
        eligible = []

        for tracking_list in all_lists:
            config = tracking_list.monitoring_config or {}
            if not config.get("enabled", False):
                skipped.append({
                    "list_id": str(tracking_list.id),
                    "name": tracking_list.name,
                    "reason": "monitoring_disabled",
                })
                continue

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

            # Check for an already-running detection on this list
            running_check = await db.execute(
                select(SignalDetectionRun.id).where(
                    and_(
                        SignalDetectionRun.tracking_list_id == tracking_list.id,
                        SignalDetectionRun.status.in_(["pending", "running"]),
                    )
                ).limit(1)
            )
            if running_check.scalar_one_or_none():
                skipped.append({
                    "list_id": str(tracking_list.id),
                    "name": tracking_list.name,
                    "reason": "detection_already_running",
                })
                continue

            eligible.append(tracking_list)

        # Sort eligible lists by priority
        eligible.sort(key=lambda tl: _sort_key_for_list(tl, now))

        # Cap at max_concurrent; remaining will be caught in the next cycle
        deferred_count = max(0, len(eligible) - max_concurrent)
        batch = eligible[:max_concurrent]

        for tracking_list in batch:
            config = tracking_list.monitoring_config or {}
            frequency_days = config.get("frequency_days", 7)

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

            # Update monitoring timestamps with jitter to spread lists naturally
            jitter = timedelta(seconds=random.uniform(0, 3600))
            tracking_list.last_monitored_at = now
            tracking_list.next_monitor_due = now + timedelta(days=frequency_days) + jitter

            await db.flush()

            triggered.append({
                "list_id": str(tracking_list.id),
                "name": tracking_list.name,
                "user_id": str(tracking_list.user_id),
                "run_id": str(run.id),
                "company_count": tracking_list.company_count,
            })

        await db.commit()

        # Launch detection tasks with staggered delays
        for i, t in enumerate(triggered):
            if t.get("dry_run"):
                continue
            run_id = t.get("run_id")
            if run_id:
                if i > 0:
                    await asyncio.sleep(stagger_seconds)
                asyncio.create_task(execute_signal_detection(uuid_mod.UUID(run_id)))

        # Emit event bus events for each triggered list
        if triggered:
            from app.events.event_bus import bus, Events
            for t in triggered:
                if not t.get("dry_run"):
                    await bus.emit(Events.MONITORING_COMPLETED, {
                        "user_id": t.get("user_id"),
                        "list_name": t.get("name"),
                        "tracking_list_id": t.get("list_id"),
                        "signals_detected": 0,  # actual count updated by detection runner
                    })

        return {
            "triggered": len(triggered),
            "skipped": len(skipped),
            "deferred": deferred_count,
            "lists_triggered": triggered,
            "lists_skipped": skipped,
            "checked_at": now.isoformat(),
        }

    except Exception as e:
        logger.error(f"Monitoring scheduler failed: {e}", exc_info=True)
        return {"error": str(e), "triggered": 0, "skipped": 0, "deferred": 0}

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


def recommend_frequency(signal_types: list[str] | None = None) -> dict:
    """Recommend a monitoring frequency based on signal type half-lives.

    Returns a dict with recommended preset key, frequency_days, and reason.
    """
    from app.services.signal_service import SIGNAL_CONFIG

    types = signal_types if signal_types else list(SIGNAL_CONFIG.keys())
    half_lives = [
        SIGNAL_CONFIG[t]["half_life_days"]
        for t in types if t in SIGNAL_CONFIG
    ]
    if not half_lives:
        return {"preset": "weekly", "frequency_days": 7, "reason": "default"}

    min_hl = min(half_lives)
    if min_hl <= 2:
        return {"preset": "daily", "frequency_days": 1, "reason": "fast-decay signals (half-life <= 2 days)"}
    elif min_hl <= 5:
        return {"preset": "active", "frequency_days": 3, "reason": "moderate-decay signals (half-life <= 5 days)"}
    elif min_hl <= 14:
        return {"preset": "weekly", "frequency_days": 7, "reason": "standard-decay signals"}
    else:
        return {"preset": "biweekly", "frequency_days": 14, "reason": "slow-decay signals only"}
