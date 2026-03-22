"""Tools monitoring API endpoints."""
import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.tool_registry import ToolRegistry
from app.models.user import User
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
from app.auth.dependencies import get_current_super_admin

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
