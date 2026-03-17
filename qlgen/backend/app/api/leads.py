from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import List, Optional

from app.db.session import get_db
from app.models.company import Company
from app.models.company_stage import CompanyStageResult
from app.models.pipeline import PipelineRun
from app.models.user import User
from app.schemas.company import CompanyResponse, CompanyStageResultResponse, ContactResponse
from app.services.export_service import generate_xlsx, generate_csv
from app.auth.dependencies import get_current_user, get_user_from_token_param

router = APIRouter(prefix="/leads", tags=["Leads"])


def _build_company_response(company: Company) -> CompanyResponse:
    """Build a CompanyResponse from a Company model."""
    contacts = [
        ContactResponse(
            id=c.id, full_name=c.full_name, first_name=c.first_name,
            last_name=c.last_name, designation=c.designation,
            role_category=c.role_category, email=c.email, phone=c.phone,
            linkedin_url=c.linkedin_url, city=c.city, source=c.source,
            confidence=c.confidence, enrichment_status=c.enrichment_status,
        )
        for c in (company.contacts or [])
    ]

    stage_results = [
        CompanyStageResultResponse(
            id=sr.id, stage=sr.stage, status=sr.status,
            score=sr.score, reasoning=sr.reasoning,
            evidence=sr.evidence, user_override=sr.user_override,
            created_at=sr.created_at,
        )
        for sr in (company.stage_results or [])
    ]

    return CompanyResponse(
        id=company.id, name=company.name, website=company.website,
        industry=company.industry, sub_industry=company.sub_industry,
        city=company.city, state_region=company.state_region, country=company.country,
        employee_count=company.employee_count, revenue_estimate=company.revenue_estimate,
        asset_value=company.asset_value,
        tech_stack_json=company.tech_stack_json, source=company.source,
        qualification=company.qualification, icp_match_score=company.icp_match_score,
        match_reasoning=company.match_reasoning, contacts=contacts,
        promoted=company.promoted, description=company.description,
        raw_data_json=company.raw_data_json, rejection_reason=company.rejection_reason,
        disqualification_stage=company.disqualification_stage, created_at=company.created_at,
        current_stage=company.current_stage,
        budget_signal_score=company.budget_signal_score,
        urgency_signal_score=company.urgency_signal_score,
        final_score=company.final_score, final_rank=company.final_rank,
        cached_from_run_id=company.cached_from_run_id,
        data_freshness=company.data_freshness,
        stage_results=stage_results,
    )


@router.get("/{run_id}/companies", response_model=List[CompanyResponse])
async def get_lead_companies(
    run_id: UUID,
    min_final_score: Optional[float] = Query(None),
    industry_filter: Optional[str] = Query(None),
    stage_filter: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("final_score"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    run_result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = run_result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    query = (
        select(Company)
        .where(Company.pipeline_run_id == run_id)
        .where(Company.qualification != "disqualified")
        .options(
            selectinload(Company.contacts),
            selectinload(Company.stage_results),
        )
    )

    if industry_filter:
        query = query.where(Company.industry.ilike(f"%{industry_filter}%"))
    if stage_filter:
        query = query.where(Company.current_stage == stage_filter)
    if min_final_score is not None:
        query = query.where(Company.final_score >= min_final_score)

    result = await db.execute(query)
    companies = result.scalars().unique().all()

    response = [_build_company_response(c) for c in companies]

    # Sort
    if sort_by == "final_score":
        response.sort(key=lambda c: c.final_score or 0, reverse=True)
    elif sort_by == "company_name":
        response.sort(key=lambda c: c.name)
    elif sort_by == "icp_match_score":
        response.sort(key=lambda c: c.icp_match_score or 0, reverse=True)
    elif sort_by == "budget_signal_score":
        response.sort(key=lambda c: c.budget_signal_score or 0, reverse=True)
    elif sort_by == "urgency_signal_score":
        response.sort(key=lambda c: c.urgency_signal_score or 0, reverse=True)

    return response


@router.get("/{run_id}/disqualified", response_model=List[CompanyResponse])
async def get_disqualified_companies(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    run_result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = run_result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    query = (
        select(Company)
        .where(Company.pipeline_run_id == run_id)
        .where(Company.qualification == "disqualified")
        .options(selectinload(Company.stage_results))
        .order_by(Company.icp_match_score.desc().nullslast())
    )

    result = await db.execute(query)
    companies = result.scalars().unique().all()

    return [_build_company_response(c) for c in companies]


@router.get("/{run_id}/stage-summary")
async def get_stage_summary(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Per-stage funnel summary with counts and averages."""
    run_result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = run_result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    # Get stage result counts
    stages = ["industry_discovery", "firmographic_fit", "budget_signals", "urgency_signals", "contact_discovery"]
    summary = []

    for stage in stages:
        result = await db.execute(
            select(
                CompanyStageResult.status,
                func.count(CompanyStageResult.id),
                func.avg(CompanyStageResult.score),
            )
            .join(Company, CompanyStageResult.company_id == Company.id)
            .where(Company.pipeline_run_id == run_id)
            .where(CompanyStageResult.stage == stage)
            .group_by(CompanyStageResult.status)
        )
        status_counts = {}
        total = 0
        avg_score = None
        for status, count, avg in result.all():
            status_counts[status] = count
            total += count
            if avg is not None:
                avg_score = round(float(avg), 1)

        if total > 0:
            summary.append({
                "stage": stage,
                "total": total,
                "passed": status_counts.get("passed", 0),
                "failed": status_counts.get("failed", 0),
                "promoted": status_counts.get("promoted", 0),
                "excluded": status_counts.get("excluded", 0),
                "avg_score": avg_score,
            })

    # Add cached company count
    cached_result = await db.execute(
        select(func.count(Company.id))
        .where(Company.pipeline_run_id == run_id)
        .where(Company.cached_from_run_id.isnot(None))
    )
    cached_count = cached_result.scalar() or 0

    return {
        "run_id": str(run_id),
        "signal_mode": run.signal_mode,
        "stages": summary,
        "cached_companies": cached_count,
    }


@router.get("/{run_id}/export")
async def export_leads(
    run_id: UUID,
    format: str = Query("xlsx"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_user_from_token_param),
):
    run_result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = run_result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    if format == "csv":
        buffer = await generate_csv(run_id, db)
        return StreamingResponse(
            buffer,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=qlgen_leads_{run_id}.csv"},
        )
    else:
        buffer = await generate_xlsx(run_id, db)
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=qlgen_leads_{run_id}.xlsx"},
        )
