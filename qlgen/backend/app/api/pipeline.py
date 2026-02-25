import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List

from app.db.session import get_db
from app.models.pipeline import PipelineRun
from app.models.icp import ICPConfig
from app.schemas.pipeline import PipelineRunRequest, PipelineRunResponse
from app.services.pipeline_service import execute_pipeline

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])

# In-memory store for SSE progress updates
pipeline_events: dict[str, list] = {}


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
    background_tasks.add_task(execute_pipeline, run.id, pipeline_events)

    return PipelineRunResponse(
        id=run.id,
        icp_config_id=run.icp_config_id,
        status=run.status,
        current_stage=run.current_stage,
        companies_found=run.companies_found or 0,
        contacts_found=run.contacts_found or 0,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


@router.get("/{run_id}", response_model=PipelineRunResponse)
async def get_pipeline_status(run_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return PipelineRunResponse(
        id=run.id,
        icp_config_id=run.icp_config_id,
        status=run.status,
        current_stage=run.current_stage,
        companies_found=run.companies_found or 0,
        contacts_found=run.contacts_found or 0,
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_log=run.error_log,
    )


@router.get("/{run_id}/stream")
async def stream_pipeline(run_id: UUID):
    run_id_str = str(run_id)

    async def event_generator():
        last_index = 0
        while True:
            events = pipeline_events.get(run_id_str, [])
            while last_index < len(events):
                event = events[last_index]
                event_type = event.get("type", "stage_update")
                data = json.dumps(event)
                yield f"event: {event_type}\ndata: {data}\n\n"
                last_index += 1
                if event_type == "completed" or event_type == "error":
                    return
            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history/list", response_model=List[PipelineRunResponse])
async def list_pipeline_runs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(50)
    )
    runs = result.scalars().all()
    return [
        PipelineRunResponse(
            id=run.id,
            icp_config_id=run.icp_config_id,
            status=run.status,
            current_stage=run.current_stage,
            companies_found=run.companies_found or 0,
            contacts_found=run.contacts_found or 0,
            started_at=run.started_at,
            completed_at=run.completed_at,
        )
        for run in runs
    ]
