"""Research Job API endpoints."""
import asyncio
import json
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_current_user, get_user_from_token_param
from app.models.user import User
from app.models.research_job import ResearchJob
from app.services.research_orchestrator import create_research_job, execute_research_job
from app.services.event_store import init_run, get_events

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/research", tags=["research"])


class CreateResearchRequest(BaseModel):
    company_kb_id: str
    job_type: str = "full_research"
    research_depth: str = "standard"
    config: Optional[dict] = None


@router.post("/jobs")
async def create_job(
    request: CreateResearchRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create and start a research job."""
    job = await create_research_job(
        db,
        company_kb_id=UUID(request.company_kb_id),
        user_id=user.id,
        job_type=request.job_type,
        research_depth=request.research_depth,
        config=request.config,
    )
    await db.commit()

    # Initialize SSE event store and start background task
    await init_run(str(job.id))
    asyncio.create_task(execute_research_job(job.id))

    return {
        "job_id": str(job.id),
        "status": "pending",
        "job_type": job.job_type,
    }


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get research job status and results."""
    result = await db.execute(
        select(ResearchJob).where(ResearchJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")

    return {
        "id": str(job.id),
        "company_kb_id": str(job.company_kb_id),
        "job_type": job.job_type,
        "status": job.status,
        "research_depth": job.research_depth,
        "progress": job.progress,
        "current_stage": job.current_stage,
        "signals_detected": job.signals_detected,
        "contacts_found": job.contacts_found,
        "brief_version": job.brief_version,
        "total_tool_calls": job.total_tool_calls,
        "total_cost_usd": job.total_cost_usd,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


@router.get("/jobs/{job_id}/stream")
async def stream_job(
    job_id: UUID,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_user_from_token_param),
):
    """SSE stream for research job progress."""
    run_id = str(job_id)

    async def event_generator():
        last_index = 0
        no_event_cycles = 0
        terminal = {"research_completed", "research_failed"}

        while True:
            events = await get_events(run_id, last_index)
            if events:
                no_event_cycles = 0
                for evt in events:
                    event_type = evt.get("type", "progress")
                    data = json.dumps(evt.get("data", {}))
                    yield f"event: {event_type}\ndata: {data}\n\n"
                    last_index += 1
                    if event_type in terminal:
                        return
            else:
                no_event_cycles += 1
                if no_event_cycles > 900:  # ~3 min timeout
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


@router.get("/company/{company_kb_id}")
async def list_company_jobs(
    company_kb_id: UUID,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List research jobs for a company."""
    result = await db.execute(
        select(ResearchJob)
        .where(ResearchJob.company_kb_id == company_kb_id)
        .order_by(ResearchJob.created_at.desc())
        .limit(limit)
    )
    jobs = list(result.scalars().all())
    return {
        "jobs": [
            {
                "id": str(j.id),
                "job_type": j.job_type,
                "status": j.status,
                "research_depth": j.research_depth,
                "signals_detected": j.signals_detected,
                "current_stage": j.current_stage,
                "progress": j.progress,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            }
            for j in jobs
        ],
    }
