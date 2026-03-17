import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
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
from app.models.user import User
from app.schemas.pipeline import (
    PipelineRunRequest, PipelineRunResponse, PipelineLogResponse,
    PromoteFirmographicRequest, PromoteFirstSignalRequest, PromoteSignalsRequest,
)
from app.services.pipeline_service import (
    execute_pipeline,
    resume_after_firmographic,
    resume_after_first_signal,
    resume_after_signals,
)
from app.auth.dependencies import get_current_user, get_user_from_token_param

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])

# In-memory store for SSE progress updates
pipeline_events: dict[str, list] = {}
# Set of run IDs that have been requested to cancel
cancelled_runs: set[str] = set()


def _build_run_response(run: PipelineRun) -> PipelineRunResponse:
    """Build a PipelineRunResponse from a PipelineRun model with ICP info."""
    icp = run.icp_config if hasattr(run, 'icp_config') and run.icp_config else None
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
        signal_mode=run.signal_mode,
        signal_phase=run.signal_phase,
        stage_details=run.stage_details,
    )


@router.post("/run", response_model=PipelineRunResponse)
async def start_pipeline(
    request: PipelineRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(ICPConfig).where(ICPConfig.id == request.icp_config_id))
    icp = result.scalar_one_or_none()
    if not icp:
        raise HTTPException(status_code=404, detail="ICP configuration not found")

    run = PipelineRun(
        icp_config_id=request.icp_config_id,
        status="pending",
        current_stage="pending",
        options=request.options.model_dump(),
        user_id=user.id,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    run_id_str = str(run.id)
    pipeline_events[run_id_str] = []

    background_tasks.add_task(execute_pipeline, run.id, pipeline_events, cancelled_runs)

    run.icp_config = icp
    return _build_run_response(run)


@router.get("/history/list", response_model=List[PipelineRunResponse])
async def list_pipeline_runs(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    result = await db.execute(
        select(PipelineRun)
        .options(selectinload(PipelineRun.icp_config))
        .order_by(PipelineRun.started_at.desc())
        .limit(50)
    )
    runs = result.scalars().all()
    return [_build_run_response(run) for run in runs]


@router.get("/stats/by-icp")
async def get_pipeline_stats_by_icp(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    result = await db.execute(
        select(PipelineRun)
        .options(selectinload(PipelineRun.icp_config))
        .where(
            (PipelineRun.companies_found > 0) | (PipelineRun.contacts_found > 0)
        )
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
async def get_pipeline_status(run_id: UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
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
async def delete_pipeline_run(run_id: UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    if run.status == "running":
        raise HTTPException(status_code=400, detail="Cannot delete a running pipeline")
    await db.delete(run)
    await db.commit()
    run_id_str = str(run_id)
    if run_id_str in pipeline_events:
        del pipeline_events[run_id_str]
    cancelled_runs.discard(run_id_str)
    return {"detail": "Pipeline run deleted"}


@router.post("/{run_id}/cancel")
async def cancel_pipeline(run_id: UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    if run.status not in ("running", "pending"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel pipeline with status '{run.status}'")
    cancelled_runs.add(str(run_id))
    return {"detail": "Cancellation requested"}


# ──────────────────────────────────────────────────────────────────
# Promote endpoints (3 review gates)
# ──────────────────────────────────────────────────────────────────

@router.post("/{run_id}/promote-firmographic", response_model=PipelineRunResponse)
async def promote_firmographic(
    run_id: UUID,
    request: PromoteFirmographicRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Stage 2 review: select companies and signal mode, start signal research."""
    result = await db.execute(
        select(PipelineRun)
        .options(selectinload(PipelineRun.icp_config))
        .where(PipelineRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    if run.status != "awaiting_review" or run.current_stage != "review_firmographic":
        raise HTTPException(status_code=400, detail=f"Pipeline is not awaiting firmographic review (stage: {run.current_stage})")

    if request.signal_mode not in ("budget_first", "urgency_first", "both"):
        raise HTTPException(status_code=400, detail="signal_mode must be 'budget_first', 'urgency_first', or 'both'")

    run_id_str = str(run_id)
    pipeline_events[run_id_str] = []

    background_tasks.add_task(
        resume_after_firmographic,
        run.id, request.company_ids, request.signal_mode,
        pipeline_events, cancelled_runs,
    )

    return _build_run_response(run)


@router.post("/{run_id}/promote-first-signal", response_model=PipelineRunResponse)
async def promote_first_signal(
    run_id: UUID,
    request: PromoteFirstSignalRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Serial mode: review after 1st signal → start 2nd signal research."""
    result = await db.execute(
        select(PipelineRun)
        .options(selectinload(PipelineRun.icp_config))
        .where(PipelineRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    if run.status != "awaiting_review" or run.signal_phase != "first_signal_done":
        raise HTTPException(status_code=400, detail="Pipeline is not awaiting first signal review")

    run_id_str = str(run_id)
    pipeline_events[run_id_str] = []

    background_tasks.add_task(
        resume_after_first_signal,
        run.id, request.company_ids,
        pipeline_events, cancelled_runs,
    )

    return _build_run_response(run)


@router.post("/{run_id}/promote-signals", response_model=PipelineRunResponse)
async def promote_signals(
    run_id: UUID,
    request: PromoteSignalsRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Final signal review → start Stages 4+5 (contact discovery + scoring)."""
    result = await db.execute(
        select(PipelineRun)
        .options(selectinload(PipelineRun.icp_config))
        .where(PipelineRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    if run.status != "awaiting_review":
        raise HTTPException(status_code=400, detail=f"Pipeline is not awaiting review (status: {run.status})")

    run_id_str = str(run_id)
    pipeline_events[run_id_str] = []

    background_tasks.add_task(
        resume_after_signals,
        run.id, request.company_ids,
        pipeline_events, cancelled_runs,
    )

    return _build_run_response(run)


# ──────────────────────────────────────────────────────────────────
# Companies by stage
# ──────────────────────────────────────────────────────────────────

@router.get("/{run_id}/companies-by-stage")
async def get_companies_by_stage(
    run_id: UUID,
    stage: str = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get companies for a pipeline run, optionally filtered by stage.

    When stage is specified, returns companies that have a CompanyStageResult
    entry for that stage (not just companies whose current_stage matches).
    This ensures companies are visible at every stage they've been through.
    """
    from app.schemas.company import CompanyResponse, CompanyStageResultResponse, ContactResponse
    from app.models.company_stage import CompanyStageResult as CSR

    query = (
        select(Company)
        .where(Company.pipeline_run_id == run_id)
        .options(
            selectinload(Company.contacts),
            selectinload(Company.stage_results),
        )
    )

    if stage:
        # Join on CompanyStageResult to find companies that have a result for this stage.
        # "signals" is a virtual stage that matches both budget_signals and urgency_signals.
        query = query.join(CSR, CSR.company_id == Company.id)
        if stage == "signals":
            from sqlalchemy import or_
            query = query.where(or_(CSR.stage == "budget_signals", CSR.stage == "urgency_signals"))
        else:
            query = query.where(CSR.stage == stage)
        # Deduplicate (a company may have multiple stage results matching, e.g. both budget + urgency)
        query = query.distinct()

    result = await db.execute(query)
    companies = result.scalars().unique().all()

    return [
        CompanyResponse(
            id=c.id, name=c.name, website=c.website,
            industry=c.industry, sub_industry=c.sub_industry,
            city=c.city, state_region=c.state_region, country=c.country,
            employee_count=c.employee_count, revenue_estimate=c.revenue_estimate,
            tech_stack_json=c.tech_stack_json, source=c.source,
            qualification=c.qualification, icp_match_score=c.icp_match_score,
            match_reasoning=c.match_reasoning,
            contacts=[
                ContactResponse(
                    id=ct.id, full_name=ct.full_name, first_name=ct.first_name,
                    last_name=ct.last_name, designation=ct.designation,
                    role_category=ct.role_category, email=ct.email, phone=ct.phone,
                    linkedin_url=ct.linkedin_url, city=ct.city, source=ct.source,
                    confidence=ct.confidence, enrichment_status=ct.enrichment_status,
                )
                for ct in c.contacts
            ],
            promoted=c.promoted, description=c.description,
            raw_data_json=c.raw_data_json, rejection_reason=c.rejection_reason,
            disqualification_stage=c.disqualification_stage, created_at=c.created_at,
            current_stage=c.current_stage,
            budget_signal_score=c.budget_signal_score,
            urgency_signal_score=c.urgency_signal_score,
            final_score=c.final_score, final_rank=c.final_rank,
            cached_from_run_id=c.cached_from_run_id,
            data_freshness=c.data_freshness,
            stage_results=[
                CompanyStageResultResponse(
                    id=sr.id, stage=sr.stage, status=sr.status,
                    score=sr.score, reasoning=sr.reasoning,
                    evidence=sr.evidence, user_override=sr.user_override,
                    created_at=sr.created_at,
                )
                for sr in c.stage_results
            ],
        )
        for c in companies
    ]


# ──────────────────────────────────────────────────────────────────
# Logs & SSE stream
# ──────────────────────────────────────────────────────────────────

@router.get("/{run_id}/logs", response_model=List[PipelineLogResponse])
async def get_pipeline_logs(run_id: UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    from app.models.pipeline_log import PipelineLog
    result = await db.execute(
        select(PipelineLog)
        .where(PipelineLog.pipeline_run_id == run_id)
        .order_by(PipelineLog.sequence_number)
    )
    logs = result.scalars().all()
    return [
        PipelineLogResponse(
            id=log.id, event_type=log.event_type,
            event_data=log.event_data, sequence_number=log.sequence_number,
            created_at=log.created_at,
        )
        for log in logs
    ]


@router.get("/{run_id}/stream")
async def stream_pipeline(run_id: UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_user_from_token_param)):
    run_id_str = str(run_id)

    result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = result.scalar_one_or_none()

    # Terminal events for already-finished pipelines
    terminal_stages = {
        "review_firmographic", "review_budget_signals", "review_urgency_signals", "review_signals",
    }

    if run and run.status in ("completed", "failed", "cancelled"):
        async def finished_generator():
            if run.status == "completed":
                yield f'event: completed\ndata: {json.dumps({"companies_found": run.companies_found or 0, "contacts_found": run.contacts_found or 0})}\n\n'
            elif run.status == "cancelled":
                yield f'event: cancelled\ndata: {json.dumps({"companies_found": run.companies_found or 0, "contacts_found": run.contacts_found or 0})}\n\n'
            else:
                yield f'event: error\ndata: {json.dumps({"message": run.error_log or "Pipeline failed"})}\n\n'
        return StreamingResponse(
            finished_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    if run and run.status == "awaiting_review":
        async def review_generator():
            if run.current_stage == "review_firmographic":
                yield f'event: awaiting_firmographic_review\ndata: {json.dumps({"companies_found": run.companies_found or 0})}\n\n'
            elif run.current_stage in ("review_budget_signals", "review_urgency_signals"):
                yield f'event: awaiting_first_signal_review\ndata: {json.dumps({"signal_type": run.current_stage.replace("review_", "")})}\n\n'
            elif run.current_stage == "review_signals":
                yield f'event: awaiting_signal_review\ndata: {json.dumps({"companies_found": run.companies_found or 0})}\n\n'
            else:
                yield f'event: awaiting_firmographic_review\ndata: {json.dumps({"companies_found": run.companies_found or 0})}\n\n'
        return StreamingResponse(
            review_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    async def event_generator():
        last_index = 0
        no_event_cycles = 0
        terminal_events = {
            "completed", "error", "cancelled",
            "awaiting_firmographic_review", "awaiting_first_signal_review",
            "awaiting_second_signal_review", "awaiting_signal_review",
        }
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
                    if event_type in terminal_events:
                        return
            else:
                no_event_cycles += 1
                if no_event_cycles % 25 == 0:
                    yield ": keepalive\n\n"
            await asyncio.sleep(0.2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
