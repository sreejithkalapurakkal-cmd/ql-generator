"""Signals API endpoints.

On-demand signal detection, signal feed, signal history per company,
dismiss/snooze signals.
"""
import logging
from typing import Optional
from uuid import UUID
import uuid as uuid_mod

from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.sql import func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_current_user, get_user_from_token_param
from app.models.user import User
from app.services.signal_service import (
    detect_signals_for_company,
    detect_signals_for_company_streaming,
    recompute_signal_heat_for_company,
    get_signals_for_company,
    get_signal_feed,
    get_dashboard_signal_stats,
    dismiss_signal,
    save_signal,
    unsave_signal,
    snooze_signal,
    archive_expired_signals,
    bulk_dismiss_signals,
    bulk_save_signals,
    bulk_snooze_signals,
    DEFAULT_SIGNAL_TYPES,
)
from app.services.event_store import init_run, get_events
from app.models.signal_event import SignalEvent
from app.events.event_bus import bus, Events

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/signals", tags=["signals"])


# ──────────────────────────────────────────────────────────────────
# Request schemas
# ──────────────────────────────────────────────────────────────────

class DetectRequest(BaseModel):
    signal_types: Optional[list[str]] = None
    signal_hints: Optional[dict] = None  # {budget_signals: [], urgency_signals: [], custom_hints: []}


class BulkSignalRequest(BaseModel):
    signal_ids: list[UUID]


class BulkSnoozeRequest(BaseModel):
    signal_ids: list[UUID]
    duration_hours: int = 24


class NotesRequest(BaseModel):
    notes: Optional[str] = None


# ──────────────────────────────────────────────────────────────────
# Signal detection
# ──────────────────────────────────────────────────────────────────

@router.post("/detect/{company_kb_id}")
async def detect_signals(
    company_kb_id: UUID,
    request: DetectRequest = DetectRequest(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Trigger on-demand signal detection for a single company."""
    types = request.signal_types or DEFAULT_SIGNAL_TYPES

    new_signals = await detect_signals_for_company(
        db, company_kb_id, types, signal_hints=request.signal_hints,
    )

    # Recompute heat score
    heat = await recompute_signal_heat_for_company(db, company_kb_id)

    # Create notifications for high/critical priority signals
    from app.services.notification_service import create_notification
    high_prio = [s for s in new_signals if s.priority in ("high", "critical")]
    for s in high_prio:
        await create_notification(
            db,
            user_id=user.id,
            notification_type="signal_detected",
            title=f"{s.signal_type}: {s.title[:200]}",
            body=s.summary[:300] if s.summary else None,
            signal_event_id=s.id,
        )

    await db.commit()

    return {
        "company_kb_id": str(company_kb_id),
        "signals_detected": len(new_signals),
        "signal_heat_score": heat,
        "signals": [
            {
                "id": str(s.id),
                "signal_type": s.signal_type,
                "priority": s.priority,
                "strength": s.strength,
                "title": s.title,
                "summary": s.summary,
                "source_url": s.source_url,
            }
            for s in new_signals
        ],
    }


# ──────────────────────────────────────────────────────────────────
# Streaming signal detection (SSE progress)
# ──────────────────────────────────────────────────────────────────

@router.post("/detect/{company_kb_id}/start")
async def start_detect_signals(
    company_kb_id: UUID,
    request: DetectRequest = DetectRequest(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start signal detection as a background task with SSE progress.

    Returns a run_id that can be used to connect to the SSE stream.
    """
    import asyncio

    run_id = str(uuid_mod.uuid4())
    await init_run(run_id)

    types = request.signal_types or DEFAULT_SIGNAL_TYPES

    asyncio.create_task(
        detect_signals_for_company_streaming(
            run_id,
            company_kb_id,
            user.id,
            types,
            request.signal_hints,
        )
    )

    return {"run_id": run_id, "status": "started"}


@router.get("/detect/{company_kb_id}/stream/{run_id}")
async def stream_detect_signals(
    company_kb_id: UUID,
    run_id: str,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_user_from_token_param),
):
    """SSE stream for single-company signal detection progress."""
    import asyncio
    import json
    from fastapi.responses import StreamingResponse

    async def event_generator():
        last_index = 0
        no_event_cycles = 0
        terminal_events = {"signal_detection_completed", "signal_detection_failed"}

        while True:
            events = await get_events(run_id, last_index)
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
                if no_event_cycles > 600:  # ~2 min timeout
                    yield f"event: timeout\ndata: {json.dumps({'message': 'Stream timeout'})}\n\n"
                    return
                if no_event_cycles % 25 == 0:
                    yield ": keepalive\n\n"

            await asyncio.sleep(0.2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ──────────────────────────────────────────────────────────────────
# Signal history for a company
# ──────────────────────────────────────────────────────────────────

@router.get("/company/{company_kb_id}")
async def get_company_signals(
    company_kb_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    include_archived: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get signal history for a specific company."""
    signals = await get_signals_for_company(
        db, company_kb_id, limit=limit, include_archived=include_archived,
    )

    return {
        "company_kb_id": str(company_kb_id),
        "count": len(signals),
        "signals": [
            {
                "id": str(s.id),
                "signal_type": s.signal_type,
                "signal_subtype": s.signal_subtype,
                "signal_category": s.signal_category,
                "priority": s.priority,
                "strength": s.strength,
                "title": s.title,
                "summary": s.summary,
                "evidence": s.evidence,
                "source_tool": s.source_tool,
                "source_url": s.source_url,
                "detected_at": s.detected_at.isoformat() if s.detected_at else None,
                "evidence_date": s.evidence_date.isoformat() if s.evidence_date else None,
                "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                "is_archived": s.is_archived,
                "is_dismissed": s.is_dismissed,
                "is_saved": s.is_saved,
                "is_snoozed": s.is_snoozed,
                "is_acted_on": s.is_acted_on,
                "confidence": s.confidence,
                "custom_rule_id": str(s.custom_rule_id) if s.custom_rule_id else None,
                "custom_rule_name": s.custom_rule_name,
                "region": s.region,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in signals
        ],
    }


# ──────────────────────────────────────────────────────────────────
# Signal feed (across all user's tracking lists)
# ──────────────────────────────────────────────────────────────────

@router.get("/feed")
async def signal_feed(
    signal_type: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    tab: Optional[str] = Query(None, description="Feed tab: all, today, week, saved"),
    search: Optional[str] = Query(None, description="Full-text search across title, summary, company name"),
    date_from: Optional[str] = Query(None, description="Filter signals from this date (ISO format)"),
    date_to: Optional[str] = Query(None, description="Filter signals up to this date (ISO format)"),
    company_kb_id: Optional[UUID] = Query(None, description="Filter to a single company"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get unified signal feed across all tracking lists for the current user."""
    from datetime import datetime as dt

    parsed_from = None
    parsed_to = None
    if date_from:
        try:
            parsed_from = dt.fromisoformat(date_from.replace("Z", "+00:00"))
        except ValueError:
            pass
    if date_to:
        try:
            parsed_to = dt.fromisoformat(date_to.replace("Z", "+00:00"))
        except ValueError:
            pass

    feed, total, snoozed_returned = await get_signal_feed(
        db, user.id,
        signal_type=signal_type,
        priority=priority,
        tab=tab,
        search=search,
        date_from=parsed_from,
        date_to=parsed_to,
        company_kb_id=company_kb_id,
        limit=limit,
        offset=offset,
    )

    return {
        "signals": feed,
        "total": total,
        "offset": offset,
        "limit": limit,
        "snoozed_returned_count": snoozed_returned,
    }


# ──────────────────────────────────────────────────────────────────
# Single signal detail
# ──────────────────────────────────────────────────────────────────

@router.get("/{signal_id}")
async def get_signal_detail(
    signal_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get full detail for a single signal by ID."""
    from app.models.company_knowledge_base import CompanyKnowledgeBase

    result = await db.execute(
        select(SignalEvent, CompanyKnowledgeBase.canonical_name, CompanyKnowledgeBase.normalized_domain)
        .join(CompanyKnowledgeBase, SignalEvent.company_kb_id == CompanyKnowledgeBase.id)
        .where(SignalEvent.id == signal_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(404, "Signal not found")

    s, company_name, domain = row
    return {
        "id": str(s.id),
        "company_kb_id": str(s.company_kb_id),
        "company_name": company_name,
        "company_domain": domain,
        "signal_type": s.signal_type,
        "signal_subtype": s.signal_subtype,
        "signal_category": s.signal_category,
        "priority": s.priority,
        "strength": s.strength,
        "confidence": s.confidence,
        "title": s.title,
        "headline": s.headline,
        "summary": s.summary,
        "evidence": s.evidence,
        "source_tool": s.source_tool,
        "source_url": s.source_url,
        "source_class": s.source_class,
        "region": s.region,
        "research_job_id": str(s.research_job_id) if s.research_job_id else None,
        "custom_rule_id": str(s.custom_rule_id) if s.custom_rule_id else None,
        "custom_rule_name": s.custom_rule_name,
        "detected_at": s.detected_at.isoformat() if s.detected_at else None,
        "evidence_date": s.evidence_date.isoformat() if s.evidence_date else None,
        "expires_at": s.expires_at.isoformat() if s.expires_at else None,
        "is_archived": s.is_archived,
        "is_dismissed": s.is_dismissed,
        "is_saved": s.is_saved,
        "is_snoozed": s.is_snoozed,
        "snoozed_until": s.snoozed_until.isoformat() if s.snoozed_until else None,
        "is_acted_on": s.is_acted_on,
        "acted_on_at": s.acted_on_at.isoformat() if s.acted_on_at else None,
        "notes": s.notes,
        "notes_updated_at": s.notes_updated_at.isoformat() if s.notes_updated_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


# ──────────────────────────────────────────────────────────────────
# Signal lifecycle
# ──────────────────────────────────────────────────────────────────

@router.post("/{signal_id}/dismiss")
async def dismiss(
    signal_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Dismiss a signal (mark as irrelevant)."""
    success = await dismiss_signal(db, signal_id)
    if not success:
        raise HTTPException(404, "Signal not found")
    await db.commit()
    return {"status": "dismissed"}


@router.post("/{signal_id}/save")
async def save(
    signal_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Save/bookmark a signal."""
    success = await save_signal(db, signal_id)
    if not success:
        raise HTTPException(404, "Signal not found")
    await db.commit()
    return {"status": "saved"}


@router.delete("/{signal_id}/save")
async def unsave(
    signal_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Remove save/bookmark from a signal."""
    success = await unsave_signal(db, signal_id)
    if not success:
        raise HTTPException(404, "Signal not found")
    await db.commit()
    return {"status": "unsaved"}


class SnoozeRequest(BaseModel):
    duration_hours: int = 24


@router.post("/{signal_id}/snooze")
async def snooze(
    signal_id: UUID,
    request: SnoozeRequest = SnoozeRequest(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Snooze a signal for a given duration. It will reappear after the period."""
    success = await snooze_signal(db, signal_id, request.duration_hours)
    if not success:
        raise HTTPException(404, "Signal not found")
    await db.commit()
    return {"status": "snoozed", "duration_hours": request.duration_hours}


@router.post("/{signal_id}/acted-on")
async def mark_signal_acted_on(
    signal_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark a signal as acted on (e.g., after sending outreach)."""
    from uuid import UUID as UUIDType
    result = await db.execute(select(SignalEvent).where(SignalEvent.id == UUIDType(signal_id)))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    signal.is_acted_on = True
    signal.acted_on_at = func.now()
    await db.commit()
    await bus.emit(Events.SIGNAL_ACTED_ON, {"signal_id": signal_id, "company_kb_id": str(signal.company_kb_id)})
    return {"status": "acted_on", "signal_id": signal_id}


# ──────────────────────────────────────────────────────────────────
# Dashboard stats
# ──────────────────────────────────────────────────────────────────

@router.get("/dashboard-stats")
async def dashboard_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get signal stats for the dashboard."""
    stats = await get_dashboard_signal_stats(db, user.id)
    return stats


@router.post("/archive-expired")
async def archive_expired(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Archive all expired signals. Can be called by cron."""
    count = await archive_expired_signals(db)
    await db.commit()
    return {"archived": count}


# ──────────────────────────────────────────────────────────────────
# Scheduled monitoring
# ──────────────────────────────────────────────────────────────────

@router.post("/monitoring/check")
async def check_monitoring(
    dry_run: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Check all tracking lists for overdue monitoring and trigger signal detection.

    Can be called by cron or manually. Use dry_run=true to preview.
    """
    from app.services.monitoring_scheduler import check_and_trigger_monitoring
    result = await check_and_trigger_monitoring(db, dry_run=dry_run)
    return result


class MonitoringConfigRequest(BaseModel):
    enabled: bool
    frequency_days: int = 7
    signal_types: Optional[list[str]] = None
    alert_threshold: str = "high"


@router.put("/monitoring/{tracking_list_id}")
async def configure_monitoring(
    tracking_list_id: UUID,
    request: MonitoringConfigRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Configure scheduled monitoring for a tracking list."""
    from app.services.monitoring_scheduler import configure_monitoring as config_mon
    result = await config_mon(
        db, tracking_list_id,
        enabled=request.enabled,
        frequency_days=request.frequency_days,
        signal_types=request.signal_types,
        alert_threshold=request.alert_threshold,
    )
    await db.commit()
    return result


# ──────────────────────────────────────────────────────────────────
# Signal type metadata
# ──────────────────────────────────────────────────────────────────

@router.get("/signal-types")
async def get_signal_types(user: User = Depends(get_current_user)):
    """Return signal type metadata (half-life, weight, category) and frequency presets."""
    from app.services.signal_service import SIGNAL_CONFIG
    return {
        "signal_types": {
            name: {
                "category": cfg["category"],
                "half_life_days": cfg["half_life_days"],
                "default_weight": cfg["default_weight"],
            }
            for name, cfg in SIGNAL_CONFIG.items()
        },
        "presets": [
            {
                "key": "daily",
                "label": "Daily",
                "frequency_days": 1,
                "description": "Daily scanning for time-critical signals (funding, earnings)",
            },
            {
                "key": "active",
                "label": "Every 3 days",
                "frequency_days": 3,
                "description": "Every 3 days for active deal cycles",
            },
            {
                "key": "weekly",
                "label": "Weekly",
                "frequency_days": 7,
                "description": "Weekly for standard account monitoring",
            },
            {
                "key": "biweekly",
                "label": "Biweekly",
                "frequency_days": 14,
                "description": "Biweekly for territory watch",
            },
        ],
    }


# ──────────────────────────────────────────────────────────────────
# Bulk signal actions
# ──────────────────────────────────────────────────────────────────

@router.post("/bulk/dismiss")
async def bulk_dismiss(
    request: BulkSignalRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Dismiss multiple signals at once."""
    count = await bulk_dismiss_signals(db, request.signal_ids)
    await db.commit()
    return {"status": "dismissed", "count": count}


@router.post("/bulk/save")
async def bulk_save(
    request: BulkSignalRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Save/bookmark multiple signals at once."""
    count = await bulk_save_signals(db, request.signal_ids)
    await db.commit()
    return {"status": "saved", "count": count}


@router.post("/bulk/snooze")
async def bulk_snooze(
    request: BulkSnoozeRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Snooze multiple signals at once."""
    count = await bulk_snooze_signals(db, request.signal_ids, request.duration_hours)
    await db.commit()
    return {"status": "snoozed", "count": count, "duration_hours": request.duration_hours}


# ──────────────────────────────────────────────────────────────────
# Signal notes
# ──────────────────────────────────────────────────────────────────

@router.patch("/{signal_id}/notes")
async def update_signal_notes(
    signal_id: UUID,
    request: NotesRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Add or update notes on a signal."""
    result = await db.execute(
        select(SignalEvent).where(SignalEvent.id == signal_id)
    )
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(404, "Signal not found")
    signal.notes = request.notes
    signal.notes_updated_at = func.now()
    await db.commit()
    return {
        "status": "updated",
        "signal_id": str(signal_id),
        "notes": signal.notes,
    }


# ──────────────────────────────────────────────────────────────────
# Signal correlations
# ──────────────────────────────────────────────────────────────────

@router.get("/correlations")
async def get_correlations(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get recent signal correlations across all tracked companies."""
    from app.models.activity_event import ActivityEvent
    from app.models.company_knowledge_base import CompanyKnowledgeBase

    kb_ids = []
    from app.services.signal_service import _get_user_tracked_kb_ids
    kb_ids = await _get_user_tracked_kb_ids(db, user.id)
    if not kb_ids:
        return {"correlations": [], "total": 0}

    result = await db.execute(
        select(
            ActivityEvent,
            CompanyKnowledgeBase.canonical_name,
            CompanyKnowledgeBase.normalized_domain,
        )
        .join(CompanyKnowledgeBase, ActivityEvent.company_kb_id == CompanyKnowledgeBase.id)
        .where(
            ActivityEvent.company_kb_id.in_(kb_ids),
            ActivityEvent.event_type == "correlation_found",
        )
        .order_by(ActivityEvent.created_at.desc())
        .limit(limit)
    )
    rows = result.all()

    correlations = []
    for event, company_name, domain in rows:
        detail = event.technical_detail or {}
        correlations.append({
            "id": str(event.id),
            "company_kb_id": str(event.company_kb_id),
            "company_name": company_name,
            "domain": domain,
            "narrative": event.narrative,
            "narrative_detail": event.narrative_detail,
            "rule_id": detail.get("rule_id"),
            "matched_signal_ids": detail.get("matched_signal_ids", []),
            "strength_boost": detail.get("strength_boost"),
            "confidence": event.confidence,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        })

    return {"correlations": correlations, "total": len(correlations)}


# ──────────────────────────────────────────────────────────────────
# Signal heatmap
# ──────────────────────────────────────────────────────────────────

@router.get("/heatmap")
async def get_signal_heatmap(
    days: int = Query(90, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get signal density per day for heatmap visualization."""
    from app.services.signal_service import _get_user_tracked_kb_ids
    from sqlalchemy import cast, Date

    kb_ids = await _get_user_tracked_kb_ids(db, user.id)
    if not kb_ids:
        return {"days": []}

    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            cast(func.coalesce(SignalEvent.evidence_date, SignalEvent.detected_at), Date).label("day"),
            func.count(SignalEvent.id).label("count"),
            func.max(
                select(SignalEvent.priority)
                .where(SignalEvent.id == SignalEvent.id)
                .correlate(SignalEvent)
                .scalar_subquery()
            ).label("max_priority"),
        )
        .where(
            SignalEvent.company_kb_id.in_(kb_ids),
            SignalEvent.is_archived == False,
            SignalEvent.is_dismissed == False,
            SignalEvent.is_relevant.isnot(False),  # hide validator-rejected signals
            func.coalesce(SignalEvent.evidence_date, SignalEvent.detected_at) >= cutoff,
        )
        .group_by("day")
        .order_by("day")
    )

    heatmap = []
    for row in result.all():
        heatmap.append({
            "date": row.day.isoformat() if row.day else None,
            "count": row.count,
        })

    return {"days": heatmap}
