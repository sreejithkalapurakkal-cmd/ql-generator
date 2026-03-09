import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import List

from app.db.session import get_db
from app.models.pipeline import PipelineRun
from app.models.company import Company
from app.models.icp import ICPConfig
from app.schemas.pipeline import PipelineRunRequest, PipelineRunResponse, PipelineLogResponse, PromoteCompaniesRequest
from app.services.pipeline_service import execute_pipeline, resume_pipeline_post_review

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])

# In-memory store for SSE progress updates
pipeline_events: dict[str, list] = {}
# Set of run IDs that have been requested to cancel
cancelled_runs: set[str] = set()


def _estimate_duration(options: dict | None) -> int:
    """Estimate pipeline duration in seconds based on options."""
    max_companies = (options or {}).get("max_companies", 25)
    return max_companies * 20 + 60


def _build_run_response(run: PipelineRun) -> PipelineRunResponse:
    """Build a PipelineRunResponse from a PipelineRun model with ICP info."""
    icp = run.icp_config if hasattr(run, 'icp_config') and run.icp_config else None
    options = run.options or {}
    return PipelineRunResponse(
        id=run.id,
        icp_config_id=run.icp_config_id,
        icp_name=icp.name if icp else None,
        icp_description=icp.description if icp else None,
        icp_config=icp.config_json if icp else None,
        status=run.status,
        current_stage=run.current_stage,
        companies_found=run.companies_found or 0,
        contacts_found=run.contacts_found or 0,
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_log=run.error_log,
        estimated_duration_seconds=_estimate_duration(run.options),
        pipeline_mode=options.get("pipeline_mode"),
        match_strictness=options.get("match_strictness"),
        bant_weights=options.get("bant_weights"),
        stage_details=run.stage_details,
    )


@router.post("/run", response_model=PipelineRunResponse)
async def start_pipeline(
    request: PipelineRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    # Verify ICP exists
    result = await db.execute(select(ICPConfig).where(ICPConfig.id == request.icp_config_id))
    icp = result.scalar_one_or_none()
    if not icp:
        raise HTTPException(status_code=404, detail="ICP configuration not found")

    # Create pipeline run
    run = PipelineRun(
        icp_config_id=request.icp_config_id,
        status="pending",
        current_stage="pending",
        options=request.options.model_dump(),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Initialize event list
    run_id_str = str(run.id)
    pipeline_events[run_id_str] = []

    # Start pipeline in background
    background_tasks.add_task(execute_pipeline, run.id, pipeline_events, cancelled_runs)

    # Attach icp_config for response building
    run.icp_config = icp
    return _build_run_response(run)


@router.get("/history/list", response_model=List[PipelineRunResponse])
async def list_pipeline_runs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PipelineRun)
        .options(selectinload(PipelineRun.icp_config))
        .order_by(PipelineRun.started_at.desc())
        .limit(50)
    )
    runs = result.scalars().all()
    return [_build_run_response(run) for run in runs]


@router.get("/stats/by-icp")
async def get_pipeline_stats_by_icp(db: AsyncSession = Depends(get_db)):
    """Return pipeline run statistics grouped by ICP config."""
    result = await db.execute(
        select(PipelineRun)
        .options(selectinload(PipelineRun.icp_config))
        .where(PipelineRun.status == "completed")
    )
    runs = result.scalars().all()

    icp_stats: dict = {}
    for run in runs:
        icp_id = str(run.icp_config_id)
        if icp_id not in icp_stats:
            icp_stats[icp_id] = {
                "icp_id": icp_id,
                "icp_name": run.icp_config.name if run.icp_config else "Unknown",
                "run_count": 0,
                "total_companies": 0,
                "total_contacts": 0,
                "runs": [],
            }
        icp_stats[icp_id]["run_count"] += 1
        icp_stats[icp_id]["total_companies"] += run.companies_found or 0
        icp_stats[icp_id]["total_contacts"] += run.contacts_found or 0
        icp_stats[icp_id]["runs"].append({
            "id": str(run.id),
            "status": run.status,
            "companies_found": run.companies_found or 0,
            "contacts_found": run.contacts_found or 0,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        })

    return list(icp_stats.values())


@router.get("/{run_id}", response_model=PipelineRunResponse)
async def get_pipeline_status(run_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PipelineRun)
        .options(selectinload(PipelineRun.icp_config))
        .where(PipelineRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return _build_run_response(run)


@router.delete("/{run_id}")
async def delete_pipeline_run(run_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    if run.status == "running":
        raise HTTPException(status_code=400, detail="Cannot delete a running pipeline")
    await db.delete(run)
    await db.commit()
    # Clean up in-memory events
    run_id_str = str(run_id)
    if run_id_str in pipeline_events:
        del pipeline_events[run_id_str]
    cancelled_runs.discard(run_id_str)
    return {"detail": "Pipeline run deleted"}


@router.post("/{run_id}/cancel")
async def cancel_pipeline(run_id: UUID, db: AsyncSession = Depends(get_db)):
    """Request cancellation of a running pipeline."""
    result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    if run.status not in ("running", "pending"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel pipeline with status '{run.status}'")
    run_id_str = str(run_id)
    cancelled_runs.add(run_id_str)
    return {"detail": "Cancellation requested"}


@router.post("/{run_id}/promote", response_model=PipelineRunResponse)
async def promote_companies(
    run_id: UUID,
    request: PromoteCompaniesRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Promote selected companies and resume the pipeline for Phase 2+3."""
    result = await db.execute(
        select(PipelineRun)
        .options(selectinload(PipelineRun.icp_config))
        .where(PipelineRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    if run.status != "awaiting_review":
        raise HTTPException(status_code=400, detail=f"Pipeline is not awaiting review (current status: {run.status})")

    # Mark selected companies as promoted, others as skipped
    company_result = await db.execute(
        select(Company).where(Company.pipeline_run_id == run_id)
    )
    all_companies = company_result.scalars().all()
    promoted_ids = set(request.company_ids)
    promoted_count = 0
    for company in all_companies:
        if company.id in promoted_ids:
            company.promoted = True
            promoted_count += 1
        else:
            company.promoted = False

    # Update stage_details with promotion metadata
    stage_details = run.stage_details or {}
    stage_details["promoted_company_ids"] = [str(cid) for cid in request.company_ids]
    stage_details["promoted_count"] = promoted_count
    run.stage_details = stage_details
    await db.commit()

    # Initialize SSE event list for the resumed pipeline
    run_id_str = str(run_id)
    pipeline_events[run_id_str] = []

    # Start resumed pipeline in background
    background_tasks.add_task(resume_pipeline_post_review, run.id, pipeline_events, cancelled_runs)

    return _build_run_response(run)


@router.get("/{run_id}/logs", response_model=List[PipelineLogResponse])
async def get_pipeline_logs(run_id: UUID, db: AsyncSession = Depends(get_db)):
    """Return persisted agent logs for a pipeline run."""
    from app.models.pipeline_log import PipelineLog
    result = await db.execute(
        select(PipelineLog)
        .where(PipelineLog.pipeline_run_id == run_id)
        .order_by(PipelineLog.sequence_number)
    )
    logs = result.scalars().all()
    return [
        PipelineLogResponse(
            id=log.id,
            event_type=log.event_type,
            event_data=log.event_data,
            sequence_number=log.sequence_number,
            created_at=log.created_at,
        )
        for log in logs
    ]


@router.get("/{run_id}/stream")
async def stream_pipeline(run_id: UUID, db: AsyncSession = Depends(get_db)):
    run_id_str = str(run_id)

    # Check if run is already finished — send terminal event immediately
    result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = result.scalar_one_or_none()
    if run and run.status in ("completed", "failed", "awaiting_review", "cancelled"):
        async def finished_generator():
            if run.status == "completed":
                yield f'event: completed\ndata: {json.dumps({"companies_found": run.companies_found or 0, "contacts_found": run.contacts_found or 0})}\n\n'
            elif run.status == "awaiting_review":
                yield f'event: awaiting_review\ndata: {json.dumps({"companies_found": run.companies_found or 0})}\n\n'
            elif run.status == "cancelled":
                yield f'event: cancelled\ndata: {json.dumps({"companies_found": run.companies_found or 0, "contacts_found": run.contacts_found or 0})}\n\n'
            else:
                yield f'event: error\ndata: {json.dumps({"message": run.error_log or "Pipeline failed"})}\n\n'

        return StreamingResponse(
            finished_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    async def event_generator():
        last_index = 0
        no_event_cycles = 0
        while True:
            events = pipeline_events.get(run_id_str, [])
            if last_index < len(events):
                no_event_cycles = 0
                while last_index < len(events):
                    event = events[last_index]
                    event_type = event.get("type", "stage_update")
                    data = json.dumps(event)
                    yield f"event: {event_type}\ndata: {data}\n\n"
                    last_index += 1
                    if event_type in ("completed", "error", "awaiting_review", "cancelled"):
                        return
            else:
                no_event_cycles += 1
                # Send keepalive comment every ~5 seconds to prevent connection timeout
                if no_event_cycles % 25 == 0:
                    yield ": keepalive\n\n"
            await asyncio.sleep(0.2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
