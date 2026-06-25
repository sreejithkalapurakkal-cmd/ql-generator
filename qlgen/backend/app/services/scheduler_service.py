"""In-process APScheduler service for periodic monitoring tasks.

Runs inside the FastAPI process via the lifespan hook. Two recurring jobs:
  1. check_and_trigger_monitoring — every MONITORING_CHECK_INTERVAL_HOURS
  2. archive_expired_signals      — once daily

On startup, cleans up SignalDetectionRun records stuck in "running" status
(from a previous crash or restart).
"""
import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, update

from app.config import get_settings
from app.db.session import async_session
from app.models.signal_detection_run import SignalDetectionRun

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _cleanup_stuck_runs() -> int:
    """Mark detection runs stuck in 'running' (>30 min) as failed."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
    async with async_session() as db:
        result = await db.execute(
            update(SignalDetectionRun)
            .where(
                SignalDetectionRun.status == "running",
                SignalDetectionRun.started_at < cutoff,
            )
            .values(
                status="failed",
                error_log="Interrupted by server restart",
                completed_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()
        count = result.rowcount
        if count:
            logger.warning("Cleaned up %d stuck signal detection run(s)", count)
        return count


async def _run_monitoring_check():
    """Wrapper that calls check_and_trigger_monitoring with its own session."""
    from app.services.monitoring_scheduler import check_and_trigger_monitoring
    try:
        result = await check_and_trigger_monitoring()
        triggered = result.get("triggered", 0)
        skipped = result.get("skipped", 0)
        if triggered:
            logger.info(
                "Monitoring check: triggered %d list(s), skipped %d",
                triggered, skipped,
            )
        else:
            logger.debug("Monitoring check: nothing due (%d skipped)", skipped)
    except Exception:
        logger.exception("Monitoring check failed")


async def _run_archive_expired():
    """Wrapper that archives expired signals with its own session."""
    from app.services.signal_service import archive_expired_signals
    try:
        async with async_session() as db:
            count = await archive_expired_signals(db)
            await db.commit()
        if count:
            logger.info("Archived %d expired signal(s)", count)
    except Exception:
        logger.exception("Archive expired signals failed")


async def start_scheduler():
    """Start the APScheduler with monitoring jobs."""
    global _scheduler

    settings = get_settings()
    interval_hours = settings.MONITORING_CHECK_INTERVAL_HOURS

    await _cleanup_stuck_runs()

    _scheduler = AsyncIOScheduler(timezone="UTC")

    _scheduler.add_job(
        _run_monitoring_check,
        "interval",
        hours=interval_hours,
        id="monitoring_check",
        name="Check tracking lists for overdue monitoring",
        replace_existing=True,
        max_instances=1,
    )

    _scheduler.add_job(
        _run_archive_expired,
        "interval",
        hours=24,
        id="archive_expired",
        name="Archive expired signals",
        replace_existing=True,
        max_instances=1,
    )

    _scheduler.start()
    logger.info(
        "Scheduler started — monitoring check every %d hour(s), archive daily",
        interval_hours,
    )


async def stop_scheduler():
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
        _scheduler = None
