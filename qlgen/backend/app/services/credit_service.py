from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline import PipelineRun


async def get_credit_usage_today(user_id: UUID, db: AsyncSession) -> dict:
    """Get credit usage for a user today (UTC).

    Returns dict with keys: used_today, reserved, runs_in_progress.
    """
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    sn_modes = ("sales_navigator_only", "sales_navigator_plus_qlgen")

    # Completed runs today: sum of actual credits used
    used_result = await db.execute(
        select(func.coalesce(func.sum(PipelineRun.evaboot_credits_used), 0))
        .where(
            PipelineRun.user_id == user_id,
            PipelineRun.discovery_mode.in_(sn_modes),
            PipelineRun.status == "completed",
            PipelineRun.started_at >= today_start,
        )
    )
    used_today = used_result.scalar() or 0

    # Running/pending runs today: sum of expected_result_count (reserved credits)
    reserved_result = await db.execute(
        select(func.coalesce(func.sum(PipelineRun.expected_result_count), 0))
        .where(
            PipelineRun.user_id == user_id,
            PipelineRun.discovery_mode.in_(sn_modes),
            PipelineRun.status.in_(("running", "pending")),
            PipelineRun.started_at >= today_start,
        )
    )
    reserved = reserved_result.scalar() or 0

    # Count of running/pending runs today
    count_result = await db.execute(
        select(func.count())
        .select_from(PipelineRun)
        .where(
            PipelineRun.user_id == user_id,
            PipelineRun.discovery_mode.in_(sn_modes),
            PipelineRun.status.in_(("running", "pending")),
            PipelineRun.started_at >= today_start,
        )
    )
    runs_in_progress = count_result.scalar() or 0

    return {
        "used_today": int(used_today),
        "reserved": int(reserved),
        "runs_in_progress": int(runs_in_progress),
    }
