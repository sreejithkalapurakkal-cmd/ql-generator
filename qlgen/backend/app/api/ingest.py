"""Ingest API endpoints.

Upload XLSX/CSV files or paste plain text to ingest company lists.
Multi-step flow: upload → preview + column mapping → confirm → process.
"""
import asyncio
import json
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db, async_session
from app.auth.dependencies import get_current_user, get_user_from_token_param
from app.models.user import User
from app.models.ingest_batch import IngestBatch
from app.services.ingest_service import (
    parse_xlsx,
    parse_csv,
    parse_paste,
    auto_map_columns,
    create_ingest_batch,
    process_ingest_batch,
)
from app.services.tracking_list_service import add_companies_to_list
from app.services.event_store import get_events, get_event_count, init_run
from app.services.ingest_store import set_pending_rows, pop_pending_rows

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


# ──────────────────────────────────────────────────────────────────
# Request schemas
# ──────────────────────────────────────────────────────────────────

class PasteRequest(BaseModel):
    text: str
    name: Optional[str] = None
    target_tracking_list_id: Optional[str] = None

class ConfirmRequest(BaseModel):
    batch_id: str
    column_mapping: dict[str, str]
    target_tracking_list_id: Optional[str] = None
    filter_config: Optional[dict] = None  # firmographic criteria
    signal_hypotheses: Optional[dict] = None  # {budget_signals: [], urgency_signals: [], custom_hints: []}

class AddSelectedRequest(BaseModel):
    company_kb_ids: list[str]
    target_tracking_list_id: str


# ──────────────────────────────────────────────────────────────────
# Upload file (XLSX/CSV)
# ──────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    name: Optional[str] = None,
    target_tracking_list_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload an XLSX/CSV file and get column preview + auto-mapping."""
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    content = await file.read()
    filename = file.filename.lower()

    if filename.endswith(".xlsx"):
        file_type = "xlsx"
        headers, rows = parse_xlsx(content)
    elif filename.endswith(".csv"):
        file_type = "csv"
        headers, rows = parse_csv(content)
    else:
        raise HTTPException(400, "Unsupported file type. Upload .xlsx or .csv")

    if not rows:
        raise HTTPException(400, "File is empty or has no data rows")

    mapping = auto_map_columns(headers)

    # Create batch record
    tl_id = UUID(target_tracking_list_id) if target_tracking_list_id else None
    batch = await create_ingest_batch(
        db, user.id, name, file.filename, file_type,
        headers, len(rows), mapping, tl_id,
    )
    await db.commit()

    # Store rows in Redis (shared across workers/tasks) until confirm
    await set_pending_rows(str(batch.id), rows)

    return {
        "batch_id": str(batch.id),
        "filename": file.filename,
        "file_type": file_type,
        "total_rows": len(rows),
        "headers": headers,
        "column_mapping": mapping,
        "preview_rows": rows[:10],
    }


# ──────────────────────────────────────────────────────────────────
# Paste text
# ──────────────────────────────────────────────────────────────────

@router.post("/paste")
async def paste_text(
    request: PasteRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Parse pasted text (one company per line or comma-separated)."""
    if not request.text.strip():
        raise HTTPException(400, "No text provided")

    headers, rows = parse_paste(request.text)

    if not rows:
        raise HTTPException(400, "No companies found in pasted text")

    mapping = {"company_name": "company_name", "domain": "domain"}

    tl_id = UUID(request.target_tracking_list_id) if request.target_tracking_list_id else None
    batch = await create_ingest_batch(
        db, user.id, request.name, None, "paste",
        headers, len(rows), mapping, tl_id,
    )
    await db.commit()

    await set_pending_rows(str(batch.id), rows)

    return {
        "batch_id": str(batch.id),
        "file_type": "paste",
        "total_rows": len(rows),
        "headers": headers,
        "column_mapping": mapping,
        "preview_rows": rows[:10],
    }


# ──────────────────────────────────────────────────────────────────
# Confirm column mapping and start processing
# ──────────────────────────────────────────────────────────────────

@router.post("/confirm")
async def confirm_and_process(
    request: ConfirmRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Confirm column mapping and start batch processing in background."""
    batch_id = UUID(request.batch_id)

    result = await db.execute(
        select(IngestBatch).where(IngestBatch.id == batch_id, IngestBatch.user_id == user.id)
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(404, "Batch not found")

    if batch.status != "pending":
        raise HTTPException(400, f"Batch is already {batch.status}")

    # Update column mapping and optional filter config
    batch.column_mapping = request.column_mapping
    if request.target_tracking_list_id:
        batch.target_tracking_list_id = UUID(request.target_tracking_list_id)
    if request.filter_config:
        batch.filter_config = request.filter_config
    if request.signal_hypotheses:
        batch.signal_hypotheses = request.signal_hypotheses

    # Set status to processing BEFORE response so frontend sees correct state immediately
    batch.status = "processing"
    await db.commit()

    rows = await pop_pending_rows(str(batch_id))
    if not rows:
        raise HTTPException(400, "Upload data expired. Please re-upload.")

    # Initialize SSE event store
    await init_run(str(batch_id))

    # Process in background
    user_id = user.id
    tl_id = batch.target_tracking_list_id
    mapping = request.column_mapping
    filter_cfg = request.filter_config

    async def _background_process():
        async with async_session() as bg_db:
            try:
                processed_batch = await process_ingest_batch(
                    bg_db, batch_id, rows, mapping,
                )
                await bg_db.commit()

                # Gather KB IDs from the completed event
                kb_ids: list[str] = []
                if processed_batch.status == "completed":
                    events = await get_events(str(batch_id))
                    for evt in reversed(events):
                        if evt.get("type") == "ingest_completed":
                            kb_ids = evt["data"].get("company_kb_ids", [])
                            break

                # Branch: firmographic filter OR auto-promote
                if filter_cfg and tl_id and kb_ids:
                    # Firmographic evaluation phase — research + score
                    from app.services.firmographic_filter_service import (
                        evaluate_companies_firmographic,
                    )
                    await evaluate_companies_firmographic(
                        str(batch_id),
                        [UUID(kid) for kid in kb_ids],
                        filter_cfg,
                    )
                    # Don't auto-add — user will select companies via add-selected endpoint
                else:
                    # Auto-promote to tracking list if specified (existing behavior)
                    if tl_id and kb_ids:
                        await add_companies_to_list(
                            bg_db, tl_id, user_id,
                            [UUID(kid) for kid in kb_ids],
                            added_from="upload",
                        )
                        await bg_db.commit()

                # Create notification for ingest completion
                from app.services.notification_service import create_notification
                await create_notification(
                    bg_db,
                    user_id=user_id,
                    notification_type="ingest_complete",
                    title=f"Import complete: {processed_batch.processed_rows} companies processed",
                    body=f"Matched {processed_batch.matched_kb} in KB, created {processed_batch.newly_created} new",
                    link=f"/tracking/{tl_id}" if tl_id else None,
                )
                await bg_db.commit()

            except Exception as e:
                logger.error(f"Ingest batch {batch_id} failed: {e}")
                result = await bg_db.execute(
                    select(IngestBatch).where(IngestBatch.id == batch_id)
                )
                b = result.scalar_one_or_none()
                if b:
                    b.status = "failed"
                    b.errors = [{"error": str(e)}]
                    await bg_db.commit()

    background_tasks.add_task(_background_process)

    return {
        "batch_id": str(batch_id),
        "status": "processing",
        "message": "Ingest started. Stream progress via /ingest/stream endpoint.",
    }


# ──────────────────────────────────────────────────────────────────
# SSE progress stream
# ──────────────────────────────────────────────────────────────────

@router.get("/stream/{batch_id}")
async def stream_ingest_progress(
    batch_id: UUID,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_user_from_token_param),
):
    """Stream ingest progress via SSE."""
    batch_id_str = str(batch_id)

    # Check if this batch has a firmographic filter — determines terminal events
    result = await db.execute(
        select(IngestBatch.filter_config).where(IngestBatch.id == batch_id)
    )
    row = result.one_or_none()
    has_filter = bool(row and row[0])

    # When filter is active, the stream stays open through both import and
    # firmographic phases. ingest_completed is NOT terminal in this case.
    if has_filter:
        terminal_events = {"firmographic_completed", "ingest_failed"}
    else:
        terminal_events = {"ingest_completed", "ingest_failed"}

    async def event_generator():
        last_index = 0
        no_event_cycles = 0

        while True:
            events = await get_events(batch_id_str, last_index)
            if events:
                no_event_cycles = 0
                for evt in events:
                    yield f"event: {evt.get('type', 'progress')}\ndata: {json.dumps(evt.get('data', {}))}\n\n"
                    last_index += 1

                    if evt.get("type") in terminal_events:
                        return
            else:
                no_event_cycles += 1
                if no_event_cycles > 600:  # ~10 min timeout for filter batches
                    yield f"event: timeout\ndata: {json.dumps({'message': 'Stream timeout'})}\n\n"
                    return

            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ──────────────────────────────────────────────────────────────────
# List batches (recent / by tracking list)
# ──────────────────────────────────────────────────────────────────

@router.get("/batches")
async def list_batches(
    tracking_list_id: Optional[str] = Query(None),
    has_filter: Optional[bool] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List recent ingest batches, optionally filtered by tracking list."""
    from sqlalchemy import desc

    q = select(IngestBatch).where(
        IngestBatch.user_id == user.id,
        IngestBatch.dismissed_at.is_(None),
    )
    if tracking_list_id:
        q = q.where(IngestBatch.target_tracking_list_id == UUID(tracking_list_id))
    if has_filter is True:
        q = q.where(IngestBatch.filter_config.isnot(None))
    q = q.order_by(desc(IngestBatch.created_at)).limit(limit)

    result = await db.execute(q)
    batches = result.scalars().all()

    items = []
    for b in batches:
        bf = bool(b.filter_config)
        if not bf:
            eval_status = "not_applicable"
        elif b.status == "completed" and b.enriched_count and b.enriched_count > 0:
            eval_status = "completed"
        elif b.status == "failed":
            eval_status = "failed"
        elif b.status == "processing":
            eval_status = "evaluating"
        else:
            eval_status = "not_started"

        items.append({
            "batch_id": str(b.id),
            "name": b.name,
            "status": b.status,
            "total_rows": b.total_rows,
            "has_filter": bf,
            "evaluation_status": eval_status,
            "enriched_count": b.enriched_count,
            "created_at": b.created_at.isoformat() if b.created_at else None,
            "target_tracking_list_id": str(b.target_tracking_list_id) if b.target_tracking_list_id else None,
        })

    return items


# ──────────────────────────────────────────────────────────────────
# Get batch status
# ──────────────────────────────────────────────────────────────────

@router.get("/batch/{batch_id}")
async def get_batch_status(
    batch_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get current status of an ingest batch."""
    result = await db.execute(
        select(IngestBatch).where(IngestBatch.id == batch_id, IngestBatch.user_id == user.id)
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(404, "Batch not found")

    has_filter = bool(batch.filter_config)

    # Derive evaluation status
    if not has_filter:
        evaluation_status = "not_applicable"
    elif batch.status == "completed" and batch.enriched_count and batch.enriched_count > 0:
        evaluation_status = "completed"
    elif batch.status == "failed":
        evaluation_status = "failed"
    elif batch.status == "processing":
        evaluation_status = "evaluating"
    else:
        evaluation_status = "not_started"

    return {
        "batch_id": str(batch.id),
        "name": batch.name,
        "filename": batch.filename,
        "file_type": batch.file_type,
        "status": batch.status,
        "total_rows": batch.total_rows,
        "processed_rows": batch.processed_rows,
        "matched_kb": batch.matched_kb,
        "newly_created": batch.newly_created,
        "enriched_count": batch.enriched_count,
        "filtered_count": batch.filtered_count,
        "errors": batch.errors,
        "has_filter": has_filter,
        "evaluation_status": evaluation_status,
        "filter_config": batch.filter_config,
        "target_tracking_list_id": str(batch.target_tracking_list_id) if batch.target_tracking_list_id else None,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
    }


# ──────────────────────────────────────────────────────────────────
# Dismiss a completed / failed batch
# ──────────────────────────────────────────────────────────────────

@router.post("/batch/{batch_id}/dismiss")
async def dismiss_batch(
    batch_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Soft-delete a completed or failed ingest batch so it no longer appears in listings."""
    from datetime import datetime, timezone as tz

    result = await db.execute(
        select(IngestBatch).where(IngestBatch.id == batch_id, IngestBatch.user_id == user.id)
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(404, "Batch not found")

    if batch.status not in ("completed", "failed"):
        raise HTTPException(400, "Only completed or failed batches can be dismissed")

    batch.dismissed_at = datetime.now(tz.utc)
    await db.commit()
    return {"status": "dismissed", "batch_id": str(batch_id)}


# ──────────────────────────────────────────────────────────────────
# Batch event logs (for replay on page revisit)
# ──────────────────────────────────────────────────────────────────

@router.get("/{batch_id}/logs")
async def get_batch_logs(
    batch_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Fetch persisted event logs for a batch. Used for replay on page revisit."""
    # Verify ownership
    batch_result = await db.execute(
        select(IngestBatch).where(IngestBatch.id == batch_id, IngestBatch.user_id == user.id)
    )
    if not batch_result.scalar_one_or_none():
        raise HTTPException(404, "Batch not found")

    from app.models.ingest_batch_log import IngestBatchLog

    result = await db.execute(
        select(IngestBatchLog)
        .where(IngestBatchLog.ingest_batch_id == batch_id)
        .order_by(IngestBatchLog.sequence_number)
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
# Add selected companies after firmographic filtering
# ──────────────────────────────────────────────────────────────────

@router.post("/{batch_id}/add-selected")
async def add_selected_companies(
    batch_id: UUID,
    request: AddSelectedRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Add user-selected companies to a tracking list after firmographic evaluation."""
    result = await db.execute(
        select(IngestBatch).where(IngestBatch.id == batch_id, IngestBatch.user_id == user.id)
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(404, "Batch not found")

    tl_id = UUID(request.target_tracking_list_id)
    kb_ids = [UUID(kid) for kid in request.company_kb_ids]

    await add_companies_to_list(
        db, tl_id, user.id, kb_ids, added_from="upload_filtered",
    )

    batch.filtered_count = len(kb_ids)
    await db.commit()

    return {"added": len(kb_ids), "batch_id": str(batch_id)}
