"""Tools monitoring API endpoints."""
import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.tool_registry import ToolRegistry
from app.models.pipeline import PipelineRun
from app.models.user import User
from app.config import get_settings
from app.schemas.tools import (
    ToolRegistryResponse,
    ToolRegistryUpdate,
    ToolHealthCheckResponse,
    ToolMetricsSummary,
)
from app.services.tool_registry_service import (
    ensure_tools_seeded,
    check_tool_health,
    update_tool_health,
    get_tool_metrics,
    get_tool_last_errors,
)
from app.auth.dependencies import get_current_super_admin, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tools", tags=["Tools Monitoring"])


@router.get("", response_model=list[ToolRegistryResponse])
async def list_tools(db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_super_admin)):
    """List all registered tools with usage metrics from pipeline_logs."""
    await ensure_tools_seeded(db)

    result = await db.execute(select(ToolRegistry).order_by(ToolRegistry.category, ToolRegistry.display_name))
    tools = result.scalars().all()

    metrics = await get_tool_metrics(db)
    last_errors = await get_tool_last_errors(db)

    response = []
    for tool in tools:
        tool_metrics = metrics.get(tool.tool_name, {})
        total = tool_metrics.get("total_calls", 0)
        successful = tool_metrics.get("successful_calls", 0)

        response.append(ToolRegistryResponse(
            id=tool.id,
            tool_name=tool.tool_name,
            display_name=tool.display_name,
            category=tool.category,
            requires_api_key=tool.requires_api_key,
            api_key_env_var=tool.api_key_env_var,
            base_url=tool.base_url,
            is_enabled=tool.is_enabled,
            health_status=tool.health_status,
            last_health_check_at=tool.last_health_check_at,
            last_health_message=tool.last_health_message,
            notes=tool.notes,
            rate_limit_info=tool.rate_limit_info,
            priority=tool.priority,
            effectiveness_threshold=tool.effectiveness_threshold,
            auto_disabled=tool.auto_disabled,
            created_at=tool.created_at,
            updated_at=tool.updated_at,
            total_calls=total,
            successful_calls=successful,
            failed_calls=tool_metrics.get("failed_calls", 0),
            success_rate=round(successful / total * 100, 1) if total > 0 else None,
            last_used_at=tool_metrics.get("last_used_at"),
            last_error=last_errors.get(tool.tool_name),
        ))

    return response


@router.get("/summary", response_model=ToolMetricsSummary)
async def get_tools_summary(db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_super_admin)):
    """Get summary counts of tool health statuses."""
    await ensure_tools_seeded(db)

    result = await db.execute(select(ToolRegistry))
    tools = result.scalars().all()

    summary = ToolMetricsSummary(
        total_tools=len(tools),
        healthy_count=sum(1 for t in tools if t.health_status == "healthy"),
        unhealthy_count=sum(1 for t in tools if t.health_status == "unhealthy"),
        disabled_count=sum(1 for t in tools if not t.is_enabled),
        no_api_key_count=sum(1 for t in tools if t.health_status == "no_api_key"),
        unknown_count=sum(1 for t in tools if t.health_status == "unknown"),
    )
    return summary


@router.patch("/{tool_id}", response_model=ToolRegistryResponse)
async def update_tool(tool_id: UUID, update: ToolRegistryUpdate, db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_super_admin)):
    """Update a tool's enabled status and/or notes."""
    result = await db.execute(select(ToolRegistry).where(ToolRegistry.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    if update.is_enabled is not None:
        tool.is_enabled = update.is_enabled
    if update.notes is not None:
        tool.notes = update.notes
    if update.effectiveness_threshold is not None:
        tool.effectiveness_threshold = update.effectiveness_threshold

    await db.commit()
    await db.refresh(tool)

    return ToolRegistryResponse(
        id=tool.id,
        tool_name=tool.tool_name,
        display_name=tool.display_name,
        category=tool.category,
        requires_api_key=tool.requires_api_key,
        api_key_env_var=tool.api_key_env_var,
        base_url=tool.base_url,
        is_enabled=tool.is_enabled,
        health_status=tool.health_status,
        last_health_check_at=tool.last_health_check_at,
        last_health_message=tool.last_health_message,
        notes=tool.notes,
        rate_limit_info=tool.rate_limit_info,
        created_at=tool.created_at,
        updated_at=tool.updated_at,
    )


@router.post("/{tool_id}/health-check", response_model=ToolHealthCheckResponse)
async def check_single_tool_health(tool_id: UUID, db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_super_admin)):
    """Run a health check for a single tool."""
    result = await db.execute(select(ToolRegistry).where(ToolRegistry.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    health = await check_tool_health(tool)
    await update_tool_health(db, tool, health)

    return ToolHealthCheckResponse(
        tool_name=tool.tool_name,
        status=health["status"],
        message=health["message"],
        checked_at=health["checked_at"],
    )


@router.post("/health-check-all", response_model=list[ToolHealthCheckResponse])
async def check_all_tools_health(db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_super_admin)):
    """Run health checks for all enabled tools concurrently."""
    await ensure_tools_seeded(db)

    result = await db.execute(
        select(ToolRegistry).where(ToolRegistry.is_enabled == True)
    )
    tools = result.scalars().all()

    async def _check_one(tool: ToolRegistry):
        health = await check_tool_health(tool)
        tool.health_status = health["status"]
        tool.last_health_check_at = health["checked_at"]
        tool.last_health_message = health["message"]
        return ToolHealthCheckResponse(
            tool_name=tool.tool_name,
            status=health["status"],
            message=health["message"],
            checked_at=health["checked_at"],
        )

    results = await asyncio.gather(*[_check_one(t) for t in tools])
    await db.commit()
    return list(results)


@router.delete("/{tool_id}")
async def delete_tool(tool_id: UUID, db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_super_admin)):
    """Delete a tool from the registry (hard delete)."""
    result = await db.execute(select(ToolRegistry).where(ToolRegistry.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    await db.delete(tool)
    await db.commit()
    return {"status": "deleted", "tool_name": tool.tool_name}


@router.get("/evaboot/status")
async def get_evaboot_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get Evaboot status for all authenticated users: credit balance, daily usage,
    Sales Navigator session health, and the current user's credit consumption."""
    settings = get_settings()
    configured = bool(settings.EVABOOT_API_KEY)

    # Base response when not configured
    if not configured:
        return {
            "configured": False,
            "quota": None,
            "sales_nav_sessions": [],
            "my_credits_used": 0,
            "my_run_count": 0,
            "total_credits_used": 0,
            "recent_runs": [],
        }

    # Live quota + Sales Navigator session status from Evaboot API
    quota = None
    sales_nav_sessions = []
    try:
        from app.tools.evaboot_tool import evaboot_check_quota
        raw = evaboot_check_quota()
        if "error" not in raw:
            # Response is nested: {"success": true, "quota": {...}}
            q = raw.get("quota", raw)  # fallback to raw if no nesting
            quota = {
                "credits": q.get("credits"),
                "daily_limit": q.get("daily_limit"),
                "used_today": q.get("used_today"),
                "remaining": q.get("remaining"),
            }
            # salesnavs array contains {id, status} — status is "valid" or "invalid"
            for sn in q.get("salesnavs", []):
                sales_nav_sessions.append({
                    "id": sn.get("id"),
                    "status": sn.get("status", "unknown"),
                })
        else:
            quota = {"error": raw["error"]}
    except Exception as e:
        quota = {"error": str(e)}

    # Current user's credit usage
    my_result = await db.execute(
        select(
            func.coalesce(func.sum(PipelineRun.evaboot_credits_used), 0).label("total"),
            func.count(PipelineRun.id).label("count"),
        )
        .where(PipelineRun.user_id == user.id)
        .where(PipelineRun.evaboot_credits_used > 0)
    )
    my_row = my_result.one()

    # Total across all users
    total_result = await db.execute(
        select(func.coalesce(func.sum(PipelineRun.evaboot_credits_used), 0))
        .where(PipelineRun.evaboot_credits_used > 0)
    )
    total_credits = total_result.scalar() or 0

    # Recent runs (last 10) across all users for visibility
    recent_result = await db.execute(
        select(
            PipelineRun.id,
            PipelineRun.discovery_mode,
            PipelineRun.evaboot_credits_used,
            PipelineRun.companies_found,
            PipelineRun.started_at,
            PipelineRun.user_id,
        )
        .where(PipelineRun.evaboot_credits_used > 0)
        .order_by(PipelineRun.started_at.desc().nullslast())
        .limit(10)
    )
    recent_rows = recent_result.all()

    # Resolve user names for recent runs
    run_user_ids = {r.user_id for r in recent_rows if r.user_id}
    user_map: dict = {}
    if run_user_ids:
        u_result = await db.execute(select(User).where(User.id.in_(run_user_ids)))
        for u in u_result.scalars().all():
            user_map[u.id] = u.name or u.email

    recent_runs = [
        {
            "id": str(r.id),
            "user_name": user_map.get(r.user_id, "Unknown"),
            "discovery_mode": r.discovery_mode,
            "credits_used": r.evaboot_credits_used or 0,
            "companies_found": r.companies_found or 0,
            "started_at": r.started_at.isoformat() if r.started_at else None,
        }
        for r in recent_rows
    ]

    return {
        "configured": True,
        "quota": quota,
        "sales_nav_sessions": sales_nav_sessions,
        "my_credits_used": int(my_row.total),
        "my_run_count": int(my_row.count),
        "total_credits_used": int(total_credits),
        "recent_runs": recent_runs,
    }
