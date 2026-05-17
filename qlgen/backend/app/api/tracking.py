"""Tracking List API endpoints.

CRUD for tracking lists and their memberships. Handles adding/removing
companies, outreach status updates, and list export.
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_user_from_token_param
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.services.tracking_list_service import (
    create_tracking_list,
    get_tracking_lists,
    get_tracking_list,
    update_tracking_list,
    delete_tracking_list,
    add_companies_to_list,
    remove_companies_from_list,
    get_list_members,
    update_membership,
    get_outreach_summary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tracking", tags=["tracking"])


# ──────────────────────────────────────────────────────────────────
# Request schemas
# ──────────────────────────────────────────────────────────────────

class CreateListRequest(BaseModel):
    name: str
    description: Optional[str] = None
    signal_hints: Optional[dict] = None  # {budget_signals: [], urgency_signals: [], custom_hints: [], target_roles: []}

class UpdateListRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    monitoring_config: Optional[dict] = None
    signal_hints: Optional[dict] = None

class AddMembersRequest(BaseModel):
    company_kb_ids: list[str]
    added_from: str = "manual"

class DetectSignalsRequest(BaseModel):
    company_kb_ids: Optional[list[str]] = None

class PromoteFromPipelineRequest(BaseModel):
    """Promote pipeline Company records to a tracking list.

    Bridges: Company → upsert KB → TrackingListMembership.
    """
    company_ids: list[str]  # pipeline Company.id UUIDs

class RemoveMembersRequest(BaseModel):
    membership_ids: list[str]

class UpdateMemberRequest(BaseModel):
    outreach_status: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[list] = None
    snoozed_until: Optional[str] = None


# ──────────────────────────────────────────────────────────────────
# List CRUD
# ──────────────────────────────────────────────────────────────────

@router.post("/lists")
async def create_list(
    request: CreateListRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tracking_list = await create_tracking_list(
        db, user.id, request.name, request.description,
        signal_hints=request.signal_hints,
    )
    await db.commit()
    return {
        "id": str(tracking_list.id),
        "name": tracking_list.name,
        "description": tracking_list.description,
        "company_count": 0,
        "monitoring_config": tracking_list.monitoring_config,
        "signal_hints": tracking_list.signal_hints,
        "created_at": tracking_list.created_at.isoformat() if tracking_list.created_at else None,
    }


@router.get("/lists")
async def list_tracking_lists(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    lists = await get_tracking_lists(db, user.id)
    return {
        "lists": [
            {
                "id": str(tl.id),
                "name": tl.name,
                "description": tl.description,
                "company_count": tl.company_count or 0,
                "monitoring_config": tl.monitoring_config,
                "signal_hints": tl.signal_hints,
                "last_monitored_at": tl.last_monitored_at.isoformat() if tl.last_monitored_at else None,
                "created_at": tl.created_at.isoformat() if tl.created_at else None,
                "updated_at": tl.updated_at.isoformat() if tl.updated_at else None,
            }
            for tl in lists
        ],
    }


@router.get("/lists/{list_id}")
async def get_list(
    list_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tracking_list = await get_tracking_list(db, list_id, user.id)
    if not tracking_list:
        raise HTTPException(status_code=404, detail="Tracking list not found")

    return {
        "id": str(tracking_list.id),
        "name": tracking_list.name,
        "description": tracking_list.description,
        "company_count": tracking_list.company_count or 0,
        "monitoring_config": tracking_list.monitoring_config,
        "signal_hints": tracking_list.signal_hints,
        "last_monitored_at": tracking_list.last_monitored_at.isoformat() if tracking_list.last_monitored_at else None,
        "is_active": tracking_list.is_active,
        "created_at": tracking_list.created_at.isoformat() if tracking_list.created_at else None,
        "updated_at": tracking_list.updated_at.isoformat() if tracking_list.updated_at else None,
    }


@router.put("/lists/{list_id}")
async def update_list(
    list_id: UUID,
    request: UpdateListRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tracking_list = await update_tracking_list(
        db, list_id, user.id,
        name=request.name,
        description=request.description,
        monitoring_config=request.monitoring_config,
        signal_hints=request.signal_hints,
    )
    if not tracking_list:
        raise HTTPException(status_code=404, detail="Tracking list not found")

    await db.commit()
    # Refresh to get server-generated values (updated_at with onupdate=func.now())
    await db.refresh(tracking_list)

    return {
        "id": str(tracking_list.id),
        "name": tracking_list.name,
        "description": tracking_list.description,
        "monitoring_config": tracking_list.monitoring_config,
        "signal_hints": tracking_list.signal_hints,
        "updated_at": tracking_list.updated_at.isoformat() if tracking_list.updated_at else None,
    }


@router.delete("/lists/{list_id}")
async def delete_list(
    list_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    success = await delete_tracking_list(db, list_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Tracking list not found")

    await db.commit()
    return {"status": "deleted"}


# ──────────────────────────────────────────────────────────────────
# Member management
# ──────────────────────────────────────────────────────────────────

@router.get("/lists/{list_id}/members")
async def get_members(
    list_id: UUID,
    outreach_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    industry_filter: Optional[str] = Query(None),
    sort_by: str = Query("signal_heat_score"),
    sort_order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    members, total = await get_list_members(
        db, list_id, user.id,
        outreach_status=outreach_status,
        search=search,
        industry_filter=industry_filter,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )
    return {
        "members": members,
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.post("/lists/{list_id}/members")
async def add_members(
    list_id: UUID,
    request: AddMembersRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    kb_ids = [UUID(kid) for kid in request.company_kb_ids]
    new_memberships = await add_companies_to_list(
        db, list_id, user.id, kb_ids, request.added_from,
    )
    await db.commit()
    return {
        "added": len(new_memberships),
        "membership_ids": [str(m.id) for m in new_memberships],
    }


@router.post("/lists/{list_id}/promote-from-pipeline")
async def promote_from_pipeline(
    list_id: UUID,
    request: PromoteFromPipelineRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Promote pipeline Company records to a tracking list.

    For each company: upsert into CompanyKnowledgeBase (if not already
    there), then add as TrackingListMembership.
    """
    from sqlalchemy.orm import selectinload
    from app.models.company import Company
    from app.services.company_kb_service import upsert_company_to_kb

    company_ids = [UUID(cid) for cid in request.company_ids]

    # Load companies with contacts
    result = await db.execute(
        select(Company)
        .options(selectinload(Company.contacts))
        .where(Company.id.in_(company_ids))
    )
    companies = list(result.scalars().unique().all())

    if not companies:
        raise HTTPException(404, "No companies found")

    # Upsert each into KB, collect KB IDs
    kb_ids = []
    for company in companies:
        if not company.website:
            continue
        kb_record = await upsert_company_to_kb(
            company,
            list(company.contacts) if company.contacts else [],
            company.pipeline_run_id,
            db,
        )
        if kb_record:
            kb_ids.append(kb_record.id)

    await db.flush()

    # Add to tracking list
    new_memberships = await add_companies_to_list(
        db, list_id, user.id, kb_ids, added_from="pipeline",
    )
    await db.commit()

    return {
        "promoted": len(new_memberships),
        "kb_records_created_or_updated": len(kb_ids),
        "membership_ids": [str(m.id) for m in new_memberships],
    }


@router.delete("/lists/{list_id}/members")
async def remove_members(
    list_id: UUID,
    request: RemoveMembersRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    m_ids = [UUID(mid) for mid in request.membership_ids]
    removed = await remove_companies_from_list(db, list_id, user.id, m_ids)
    await db.commit()
    return {"removed": removed}


@router.patch("/lists/{list_id}/members/{membership_id}")
async def update_member(
    list_id: UUID,
    membership_id: UUID,
    request: UpdateMemberRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from datetime import datetime

    snoozed = None
    if request.snoozed_until:
        snoozed = datetime.fromisoformat(request.snoozed_until)

    membership = await update_membership(
        db, list_id, membership_id, user.id,
        outreach_status=request.outreach_status,
        notes=request.notes,
        tags=request.tags,
        snoozed_until=snoozed,
    )
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")

    await db.commit()
    return {
        "membership_id": str(membership.id),
        "outreach_status": membership.outreach_status,
        "notes": membership.notes,
        "tags": membership.tags,
        "snoozed_until": membership.snoozed_until.isoformat() if membership.snoozed_until else None,
    }


# ──────────────────────────────────────────────────────────────────
# Outreach summary (for Kanban)
# ──────────────────────────────────────────────────────────────────

@router.get("/lists/{list_id}/outreach-summary")
async def outreach_summary(
    list_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    summary = await get_outreach_summary(db, list_id, user.id)
    return {"summary": summary}


# ──────────────────────────────────────────────────────────────────
# Contact enrichment
# ──────────────────────────────────────────────────────────────────

class EnrichRequest(BaseModel):
    target_roles: Optional[list[str]] = None
    max_companies: int = 20

class EnrichSingleRequest(BaseModel):
    target_roles: Optional[list[str]] = None


@router.post("/lists/{list_id}/enrich")
async def enrich_list(
    list_id: UUID,
    request: EnrichRequest = EnrichRequest(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Enrich contacts for all companies in a tracking list."""
    from app.services.enrichment_service import bulk_enrich_list

    result = await bulk_enrich_list(
        db, list_id, user.id,
        target_roles=request.target_roles,
        max_companies=request.max_companies,
    )
    if result.get("error"):
        raise HTTPException(404, result["error"])

    # Create notification for enrichment completion
    from app.services.notification_service import create_notification
    await create_notification(
        db,
        user_id=user.id,
        notification_type="monitoring_complete",
        title=f"Contact enrichment complete: {result.get('total_contacts_found', 0)} contacts found",
        body=f"Enriched {result.get('companies_enriched', 0)} companies in tracking list",
        link=f"/tracking/{list_id}",
    )

    await db.commit()
    return result


@router.post("/lists/{list_id}/members/{membership_id}/enrich")
async def enrich_member(
    list_id: UUID,
    membership_id: UUID,
    request: EnrichSingleRequest = EnrichSingleRequest(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Enrich contacts for a single tracked company."""
    from app.services.enrichment_service import enrich_company_contacts
    from app.models.tracking_list_membership import TrackingListMembership

    # Verify ownership
    tracking_list = await get_tracking_list(db, list_id, user.id)
    if not tracking_list:
        raise HTTPException(404, "Tracking list not found")

    result = await db.execute(
        select(TrackingListMembership).where(
            TrackingListMembership.id == membership_id,
            TrackingListMembership.tracking_list_id == list_id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(404, "Membership not found")

    membership.enrichment_status = "in_progress"
    await db.flush()

    try:
        enrichment = await enrich_company_contacts(
            db, membership.company_kb_id, request.target_roles,
        )
        membership.enrichment_status = "enriched"

        # Create notification for single-company enrichment
        from app.services.notification_service import create_notification
        await create_notification(
            db,
            user_id=user.id,
            notification_type="monitoring_complete",
            title=f"Contacts found for {enrichment.get('company_name', 'company')}",
            body=f"{enrichment.get('contacts_found', 0)} new contacts discovered",
            link=f"/tracking/{list_id}",
        )

        await db.commit()
        return enrichment
    except Exception as e:
        membership.enrichment_status = "failed"
        await db.commit()
        raise HTTPException(500, f"Enrichment failed: {str(e)}")


@router.get("/lists/{list_id}/members/{membership_id}/contacts")
async def get_member_contacts(
    list_id: UUID,
    membership_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get enriched contacts for a tracked company."""
    from app.models.tracking_list_membership import TrackingListMembership
    from app.models.company_knowledge_base import CompanyKnowledgeBase

    tracking_list = await get_tracking_list(db, list_id, user.id)
    if not tracking_list:
        raise HTTPException(404, "Tracking list not found")

    result = await db.execute(
        select(TrackingListMembership, CompanyKnowledgeBase)
        .join(CompanyKnowledgeBase, TrackingListMembership.company_kb_id == CompanyKnowledgeBase.id)
        .where(
            TrackingListMembership.id == membership_id,
            TrackingListMembership.tracking_list_id == list_id,
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(404, "Membership not found")

    membership, kb = row
    contacts = kb.best_known_contacts or []

    return {
        "company_kb_id": str(kb.id),
        "company_name": kb.canonical_name,
        "enrichment_status": membership.enrichment_status,
        "contacts": contacts,
        "total": len(contacts),
        "last_enriched_at": kb.last_enriched_at.isoformat() if kb.last_enriched_at else None,
    }


# ──────────────────────────────────────────────────────────────────
# Signal detection (background task with SSE progress)
# ──────────────────────────────────────────────────────────────────

@router.post("/lists/{list_id}/detect-signals")
async def detect_signals_for_list(
    list_id: UUID,
    request: DetectSignalsRequest = DetectSignalsRequest(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start background signal detection for companies in a list.

    If request.company_kb_ids is provided, only scan those companies (up to 20).
    Otherwise, scan all companies in the list (up to 20).
    """
    import asyncio
    import uuid as uuid_mod
    from app.models.signal_detection_run import SignalDetectionRun
    from app.models.tracking_list_membership import TrackingListMembership
    from app.services.signal_detection_runner import execute_signal_detection
    from app.services.event_store import init_run

    tracking_list = await get_tracking_list(db, list_id, user.id)
    if not tracking_list:
        raise HTTPException(404, "Tracking list not found")

    if request.company_kb_ids:
        # Selective detection: use provided IDs (limit 20), verified against list membership
        requested_ids = [UUID(kid) for kid in request.company_kb_ids[:20]]
        members_result = await db.execute(
            select(TrackingListMembership.company_kb_id).where(
                TrackingListMembership.tracking_list_id == list_id,
                TrackingListMembership.company_kb_id.in_(requested_ids),
            )
        )
        kb_ids = [row[0] for row in members_result.all()]
    else:
        # Full list detection
        members_result = await db.execute(
            select(TrackingListMembership.company_kb_id).where(
                TrackingListMembership.tracking_list_id == list_id,
            ).limit(20)
        )
        kb_ids = [row[0] for row in members_result.all()]

    if not kb_ids:
        raise HTTPException(400, "No companies to scan")

    # Create run record
    run = SignalDetectionRun(
        id=uuid_mod.uuid4(),
        tracking_list_id=list_id,
        user_id=user.id,
        status="pending",
        total_companies=len(kb_ids),
    )
    db.add(run)
    await db.commit()

    # Initialize SSE event store
    await init_run(str(run.id))

    # Schedule on event loop directly
    run_id_copy = run.id  # ensure plain UUID, not lazy SQLAlchemy attr
    logger.info(f"[detect-signals] Creating async task for run {run_id_copy}")
    try:
        task = asyncio.create_task(execute_signal_detection(run_id_copy))
        logger.info(f"[detect-signals] Task created: {task!r}")
    except Exception as e:
        logger.error(f"[detect-signals] Failed to create task: {e}", exc_info=True)

    return {
        "run_id": str(run.id),
        "status": "started",
        "total_companies": len(kb_ids),
    }


@router.get("/lists/{list_id}/signal-detection/{run_id}/stream")
async def stream_signal_detection(
    list_id: UUID,
    run_id: UUID,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_user_from_token_param),
):
    """SSE stream for signal detection progress."""
    import asyncio
    import json
    from app.services.event_store import get_events

    run_id_str = str(run_id)

    async def event_generator():
        last_index = 0
        no_event_cycles = 0
        terminal_events = {
            "signal_detection_completed",
            "signal_detection_failed",
            "signal_detection_cancelled",
        }

        while True:
            events = await get_events(run_id_str, last_index)
            if events:
                no_event_cycles = 0
                for evt in events:
                    event_type = evt.get("type", "signal_progress")
                    data = json.dumps(evt.get("data", {}))
                    yield f"event: {event_type}\ndata: {data}\n\n"
                    last_index += 1

                    if event_type in terminal_events:
                        return
            else:
                no_event_cycles += 1
                if no_event_cycles > 600:  # ~2 minutes with 0.2s sleep
                    yield f"event: timeout\ndata: {json.dumps({'message': 'Stream timeout'})}\n\n"
                    return
                if no_event_cycles % 25 == 0:
                    yield ": keepalive\n\n"

            await asyncio.sleep(0.2)

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/lists/{list_id}/signal-detection/latest")
async def get_latest_signal_detection(
    list_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get the most recent signal detection run for a tracking list."""
    from app.models.signal_detection_run import SignalDetectionRun

    result = await db.execute(
        select(SignalDetectionRun)
        .where(
            SignalDetectionRun.tracking_list_id == list_id,
            SignalDetectionRun.user_id == user.id,
        )
        .order_by(SignalDetectionRun.created_at.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if not run:
        return {"run": None}

    return {
        "run": {
            "run_id": str(run.id),
            "status": run.status,
            "total_companies": run.total_companies,
            "processed_companies": run.processed_companies,
            "signals_detected": run.signals_detected,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        },
    }


@router.get("/lists/{list_id}/signal-detection/{run_id}")
async def get_signal_detection_run(
    list_id: UUID,
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get status of a signal detection run."""
    from app.models.signal_detection_run import SignalDetectionRun

    result = await db.execute(
        select(SignalDetectionRun).where(
            SignalDetectionRun.id == run_id,
            SignalDetectionRun.tracking_list_id == list_id,
            SignalDetectionRun.user_id == user.id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "Signal detection run not found")

    return {
        "run_id": str(run.id),
        "status": run.status,
        "total_companies": run.total_companies,
        "processed_companies": run.processed_companies,
        "signals_detected": run.signals_detected,
        "use_agent": run.use_agent,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


@router.post("/lists/{list_id}/signal-detection/{run_id}/cancel")
async def cancel_signal_detection(
    list_id: UUID,
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Cancel a running signal detection."""
    from app.services.event_store import mark_cancelled

    await mark_cancelled(str(run_id))
    return {"status": "cancellation_requested"}


@router.get("/lists/{list_id}/signal-detection/{run_id}/logs")
async def get_signal_detection_logs(
    list_id: UUID,
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Fetch persisted event logs for a signal detection run. Used for replay on page revisit."""
    from app.models.signal_detection_run import SignalDetectionRun
    from app.models.signal_detection_log import SignalDetectionLog

    # Verify ownership
    run_result = await db.execute(
        select(SignalDetectionRun).where(
            SignalDetectionRun.id == run_id,
            SignalDetectionRun.tracking_list_id == list_id,
            SignalDetectionRun.user_id == user.id,
        )
    )
    if not run_result.scalar_one_or_none():
        raise HTTPException(404, "Signal detection run not found")

    result = await db.execute(
        select(SignalDetectionLog)
        .where(SignalDetectionLog.signal_detection_run_id == run_id)
        .order_by(SignalDetectionLog.sequence_number)
    )
    logs = result.scalars().all()

    return [
        {
            "event_type": log.event_type,
            "event_data": log.event_data,
            "sequence_number": log.sequence_number,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


# ──────────────────────────────────────────────────────────────────
# Async contact enrichment (background task with SSE progress)
# ──────────────────────────────────────────────────────────────────

class EnrichAsyncRequest(BaseModel):
    target_roles: Optional[list[str]] = None
    max_companies: int = 20


@router.post("/lists/{list_id}/enrich-async")
async def enrich_list_async(
    list_id: UUID,
    request: EnrichAsyncRequest = EnrichAsyncRequest(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start background contact enrichment for companies in a list.

    Returns immediately with a run_id. Connect to the SSE stream for progress.
    """
    import asyncio
    import uuid as uuid_mod
    from app.models.enrichment_run import EnrichmentRun
    from app.models.tracking_list_membership import TrackingListMembership
    from app.services.enrichment_runner import execute_enrichment
    from app.services.event_store import init_run

    tracking_list = await get_tracking_list(db, list_id, user.id)
    if not tracking_list:
        raise HTTPException(404, "Tracking list not found")

    # Count members
    members_result = await db.execute(
        select(TrackingListMembership.id).where(
            TrackingListMembership.tracking_list_id == list_id,
        ).limit(request.max_companies)
    )
    member_count = len(members_result.all())

    if not member_count:
        raise HTTPException(400, "No companies to enrich")

    # Create run record
    run = EnrichmentRun(
        id=uuid_mod.uuid4(),
        tracking_list_id=list_id,
        user_id=user.id,
        status="pending",
        total_companies=member_count,
        target_roles=request.target_roles,
    )
    db.add(run)
    await db.commit()

    # Initialize SSE event store
    await init_run(str(run.id))

    # Schedule on event loop directly
    asyncio.create_task(execute_enrichment(run.id))

    return {
        "run_id": str(run.id),
        "status": "started",
        "total_companies": member_count,
    }


@router.get("/lists/{list_id}/enrichment/{run_id}/stream")
async def stream_enrichment(
    list_id: UUID,
    run_id: UUID,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_user_from_token_param),
):
    """SSE stream for enrichment progress."""
    import asyncio
    import json
    from app.services.event_store import get_events

    run_id_str = str(run_id)

    async def event_generator():
        last_index = 0
        no_event_cycles = 0
        terminal_events = {
            "enrichment_completed",
            "enrichment_failed",
            "enrichment_cancelled",
        }

        while True:
            events = await get_events(run_id_str, last_index)
            if events:
                no_event_cycles = 0
                for evt in events:
                    event_type = evt.get("type", "enrichment_progress")
                    data = json.dumps(evt.get("data", {}))
                    yield f"event: {event_type}\ndata: {data}\n\n"
                    last_index += 1

                    if event_type in terminal_events:
                        return
            else:
                no_event_cycles += 1
                if no_event_cycles > 600:  # ~2 minutes with 0.2s sleep
                    yield f"event: timeout\ndata: {json.dumps({'message': 'Stream timeout'})}\n\n"
                    return
                if no_event_cycles % 25 == 0:
                    yield ": keepalive\n\n"

            await asyncio.sleep(0.2)

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/lists/{list_id}/enrichment/latest")
async def get_latest_enrichment(
    list_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get the most recent enrichment run for a tracking list."""
    from app.models.enrichment_run import EnrichmentRun

    result = await db.execute(
        select(EnrichmentRun)
        .where(
            EnrichmentRun.tracking_list_id == list_id,
            EnrichmentRun.user_id == user.id,
        )
        .order_by(EnrichmentRun.created_at.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if not run:
        return {"run": None}

    return {
        "run": {
            "run_id": str(run.id),
            "status": run.status,
            "total_companies": run.total_companies,
            "processed_companies": run.processed_companies,
            "contacts_found": run.contacts_found,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        },
    }


@router.get("/lists/{list_id}/enrichment/{run_id}")
async def get_enrichment_run(
    list_id: UUID,
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get status of an enrichment run."""
    from app.models.enrichment_run import EnrichmentRun

    result = await db.execute(
        select(EnrichmentRun).where(
            EnrichmentRun.id == run_id,
            EnrichmentRun.tracking_list_id == list_id,
            EnrichmentRun.user_id == user.id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "Enrichment run not found")

    return {
        "run_id": str(run.id),
        "status": run.status,
        "total_companies": run.total_companies,
        "processed_companies": run.processed_companies,
        "contacts_found": run.contacts_found,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


@router.get("/lists/{list_id}/enrichment/{run_id}/logs")
async def get_enrichment_logs(
    list_id: UUID,
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Fetch persisted event logs for an enrichment run. Used for replay on page revisit."""
    from app.models.enrichment_run import EnrichmentRun
    from app.models.enrichment_log import EnrichmentLog

    # Verify ownership
    run_result = await db.execute(
        select(EnrichmentRun).where(
            EnrichmentRun.id == run_id,
            EnrichmentRun.tracking_list_id == list_id,
            EnrichmentRun.user_id == user.id,
        )
    )
    if not run_result.scalar_one_or_none():
        raise HTTPException(404, "Enrichment run not found")

    result = await db.execute(
        select(EnrichmentLog)
        .where(EnrichmentLog.enrichment_run_id == run_id)
        .order_by(EnrichmentLog.sequence_number)
    )
    logs = result.scalars().all()

    return [
        {
            "event_type": log.event_type,
            "event_data": log.event_data,
            "sequence_number": log.sequence_number,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


@router.post("/lists/{list_id}/enrichment/{run_id}/cancel")
async def cancel_enrichment(
    list_id: UUID,
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Cancel a running enrichment."""
    from app.services.event_store import mark_cancelled

    await mark_cancelled(str(run_id))
    return {"status": "cancellation_requested"}
