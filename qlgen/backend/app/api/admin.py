"""Admin-only endpoints for audit logs and user activity."""
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.icp import ICPConfig
from app.models.pipeline import PipelineRun
from app.auth.dependencies import get_current_super_admin

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/audit-logs")
async def get_audit_logs(
    resource_type: Optional[str] = Query(None),
    user_id: Optional[UUID] = Query(None),
    limit: int = Query(100, le=500),
    _admin: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get audit logs (super_admin only)."""
    query = select(AuditLog).order_by(AuditLog.created_at.desc())

    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)

    query = query.limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    # Fetch user names for the logs
    user_ids = {log.user_id for log in logs if log.user_id}
    user_map = {}
    if user_ids:
        user_result = await db.execute(select(User).where(User.id.in_(user_ids)))
        for u in user_result.scalars().all():
            user_map[u.id] = {"name": u.name, "email": u.email}

    return [
        {
            "id": str(log.id),
            "user_id": str(log.user_id) if log.user_id else None,
            "user_name": user_map.get(log.user_id, {}).get("name") if log.user_id else None,
            "user_email": user_map.get(log.user_id, {}).get("email") if log.user_id else None,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": str(log.resource_id) if log.resource_id else None,
            "details": log.details,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


@router.get("/activity")
async def get_admin_activity(
    _admin: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get admin activity overview: user summaries, recent runs, recent ICPs."""
    # User summaries
    users_result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = users_result.scalars().all()

    user_summaries = []
    for u in users:
        icp_count = (await db.execute(
            select(func.count(ICPConfig.id)).where(ICPConfig.user_id == u.id, ICPConfig.is_active == True)
        )).scalar() or 0

        pipeline_count = (await db.execute(
            select(func.count(PipelineRun.id)).where(PipelineRun.user_id == u.id)
        )).scalar() or 0

        last_run = (await db.execute(
            select(PipelineRun.started_at)
            .where(PipelineRun.user_id == u.id)
            .order_by(PipelineRun.started_at.desc().nullslast())
            .limit(1)
        )).scalar()

        user_summaries.append({
            "user_id": str(u.id),
            "user_name": u.name,
            "user_email": u.email,
            "role": u.role,
            "icp_count": icp_count,
            "pipeline_count": pipeline_count,
            "last_activity": last_run.isoformat() if last_run else (u.last_login_at.isoformat() if u.last_login_at else None),
        })

    # Recent pipeline runs (across all users)
    runs_result = await db.execute(
        select(PipelineRun)
        .options(selectinload(PipelineRun.icp_config))
        .order_by(PipelineRun.started_at.desc().nullslast())
        .limit(20)
    )
    runs = runs_result.scalars().all()

    # Collect user IDs for runs
    run_user_ids = {r.user_id for r in runs if r.user_id}
    run_user_map = {}
    if run_user_ids:
        u_result = await db.execute(select(User).where(User.id.in_(run_user_ids)))
        for u in u_result.scalars().all():
            run_user_map[u.id] = u.name or u.email

    recent_runs = [
        {
            "id": str(r.id),
            "icp_name": r.icp_config.name if r.icp_config else None,
            "user_name": run_user_map.get(r.user_id),
            "status": r.status,
            "companies_found": r.companies_found or 0,
            "contacts_found": r.contacts_found or 0,
            "started_at": r.started_at.isoformat() if r.started_at else None,
        }
        for r in runs
    ]

    # Recent ICP creations
    icps_result = await db.execute(
        select(ICPConfig)
        .where(ICPConfig.is_active == True)
        .order_by(ICPConfig.created_at.desc())
        .limit(20)
    )
    icps = icps_result.scalars().all()

    icp_user_ids = {i.user_id for i in icps if i.user_id}
    icp_user_map = {}
    if icp_user_ids:
        u_result = await db.execute(select(User).where(User.id.in_(icp_user_ids)))
        for u in u_result.scalars().all():
            icp_user_map[u.id] = u.name or u.email

    recent_icps = [
        {
            "id": str(i.id),
            "name": i.name,
            "user_name": icp_user_map.get(i.user_id),
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in icps
    ]

    return {
        "user_summaries": user_summaries,
        "recent_runs": recent_runs,
        "recent_icps": recent_icps,
    }
