from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, case
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import List, Optional

from app.db.session import get_db
from app.models.company import Company
from app.models.company_stage import CompanyStageResult
from app.models.pipeline import PipelineRun
from app.models.pipeline_log import PipelineLog
from app.models.discovery_intelligence import ToolEffectiveness
from app.models.user import User
from app.schemas.company import CompanyResponse, CompanyStageResultResponse, ContactResponse
from app.services.export_service import generate_xlsx, generate_csv
from app.auth.dependencies import get_current_user, get_user_from_token_param
from app.auth.authorization import check_resource_access

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
        recency_adjusted_budget_score=company.recency_adjusted_budget_score,
        recency_adjusted_urgency_score=company.recency_adjusted_urgency_score,
        deal_hotness_score=company.deal_hotness_score,
        deal_hotness_tier=company.deal_hotness_tier,
        avg_evidence_age_months=company.avg_evidence_age_months,
    )


async def _get_run_with_access_check(run_id: UUID, db: AsyncSession, user: User) -> PipelineRun:
    """Fetch a pipeline run and verify the user has access."""
    run_result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = run_result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    check_resource_access(run.user_id, user)
    return run


@router.get("/{run_id}/companies", response_model=List[CompanyResponse])
async def get_lead_companies(
    run_id: UUID,
    min_final_score: Optional[float] = Query(None),
    industry_filter: Optional[str] = Query(None),
    stage_filter: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("final_score"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_run_with_access_check(run_id, db, user)

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
    elif sort_by == "deal_hotness_score":
        response.sort(key=lambda c: c.deal_hotness_score or 0, reverse=True)

    return response


@router.get("/{run_id}/disqualified", response_model=List[CompanyResponse])
async def get_disqualified_companies(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_run_with_access_check(run_id, db, user)

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
    user: User = Depends(get_current_user),
):
    """Per-stage funnel summary with counts and averages."""
    run = await _get_run_with_access_check(run_id, db, user)

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
    scope: str = Query("all", description="Export scope: 'all' for every company, 'final' for qualified/promoted only"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_user_from_token_param),
):
    await _get_run_with_access_check(run_id, db, user)

    suffix = "final" if scope == "final" else "all"
    if format == "csv":
        buffer = await generate_csv(run_id, db, scope=scope)
        return StreamingResponse(
            buffer,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=qlgen_leads_{suffix}_{run_id}.csv"},
        )
    else:
        buffer = await generate_xlsx(run_id, db, scope=scope)
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=qlgen_leads_{suffix}_{run_id}.xlsx"},
        )


@router.get("/tool-effectiveness")
async def get_tool_effectiveness_aggregate(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Cross-run aggregate tool effectiveness metrics."""
    result = await db.execute(
        select(ToolEffectiveness)
        .where(ToolEffectiveness.total_companies_sourced >= 1)
        .order_by(ToolEffectiveness.effectiveness_score.desc())
    )
    rows = result.scalars().all()

    tools = []
    for te in rows:
        pass_rate = round(te.companies_passed_stage2 / max(te.total_companies_sourced, 1) * 100, 1)
        tools.append({
            "tool_name": te.tool_name,
            "industry": te.industry,
            "country": te.country,
            "total_companies_sourced": te.total_companies_sourced,
            "companies_passed_stage2": te.companies_passed_stage2,
            "pass_rate": pass_rate,
            "avg_score": te.avg_final_score,
            "effectiveness_score": te.effectiveness_score,
            "total_runs_used": te.total_runs_used,
        })

    return {"tools": tools}


@router.get("/{run_id}/tool-attribution")
async def get_tool_attribution(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Per-tool company attribution for a pipeline run.

    Returns which tools contributed how many companies and their quality
    breakdown (high/medium/low fit) based on icp_match_score.
    """
    await _get_run_with_access_check(run_id, db, user)

    # Query company attribution grouped by source
    result = await db.execute(
        select(
            Company.source,
            func.count(Company.id).label("total"),
            func.count(case((Company.qualification != "disqualified", Company.id))).label("qualified"),
            func.count(case((Company.qualification == "disqualified", Company.id))).label("disqualified"),
            func.count(case((Company.icp_match_score >= 70, Company.id))).label("high_fit"),
            func.count(case((
                and_(Company.icp_match_score >= 40, Company.icp_match_score < 70), Company.id
            ))).label("medium_fit"),
            func.count(case((Company.icp_match_score < 40, Company.id))).label("low_fit"),
            func.avg(Company.icp_match_score).label("avg_score"),
        )
        .where(Company.pipeline_run_id == run_id)
        .group_by(Company.source)
        .order_by(func.count(Company.id).desc())
    )

    tools = []
    for row in result.all():
        source = row.source or "unknown"

        # Get top 3 highest-scoring company names for this tool
        sample_result = await db.execute(
            select(Company.name)
            .where(Company.pipeline_run_id == run_id)
            .where(Company.source == row.source)
            .where(Company.qualification != "disqualified")
            .order_by(Company.icp_match_score.desc().nullslast())
            .limit(3)
        )
        sample_names = [r[0] for r in sample_result.all()]

        efficiency = round(row.qualified / max(row.total, 1) * 100, 1)

        tools.append({
            "tool_name": source,
            "companies_discovered": row.total,
            "companies_qualified": row.qualified,
            "companies_disqualified": row.disqualified,
            "high_fit_count": row.high_fit,
            "medium_fit_count": row.medium_fit,
            "low_fit_count": row.low_fit,
            "avg_icp_match_score": round(float(row.avg_score), 1) if row.avg_score else None,
            "efficiency": efficiency,
            "sample_companies": sample_names,
        })

    # Get tool call stats from pipeline_logs
    log_result = await db.execute(
        select(
            PipelineLog.event_data["tool_name"].astext.label("tool_name"),
            func.count(PipelineLog.id).label("total_calls"),
            func.count(case((PipelineLog.event_type == "tool_error", PipelineLog.id))).label("error_calls"),
        )
        .where(PipelineLog.pipeline_run_id == run_id)
        .where(PipelineLog.event_type.in_(["tool_result", "tool_error"]))
        .group_by(PipelineLog.event_data["tool_name"].astext)
    )

    call_stats = {}
    for row in log_result.all():
        if row.tool_name:
            successful = row.total_calls - row.error_calls
            call_stats[row.tool_name] = {
                "total_calls": row.total_calls,
                "successful_calls": successful,
                "failed_calls": row.error_calls,
                "success_rate": round(successful / row.total_calls * 100, 1) if row.total_calls > 0 else 0,
            }

    # Merge call stats into tool attribution data
    for tool in tools:
        stats = call_stats.pop(tool["tool_name"], {})
        tool["total_calls"] = stats.get("total_calls", 0)
        tool["successful_calls"] = stats.get("successful_calls", 0)
        tool["failed_calls"] = stats.get("failed_calls", 0)
        tool["success_rate"] = stats.get("success_rate", None)

    # Add tools that had calls but no company attributions (e.g. tools used
    # in Stage 2 enrichment that don't set Company.source)
    for tool_name, stats in call_stats.items():
        tools.append({
            "tool_name": tool_name,
            "companies_discovered": 0,
            "companies_qualified": 0,
            "companies_disqualified": 0,
            "high_fit_count": 0,
            "medium_fit_count": 0,
            "low_fit_count": 0,
            "avg_icp_match_score": None,
            "efficiency": None,
            "sample_companies": [],
            "total_calls": stats["total_calls"],
            "successful_calls": stats["successful_calls"],
            "failed_calls": stats["failed_calls"],
            "success_rate": stats["success_rate"],
        })

    return {
        "run_id": str(run_id),
        "tools": tools,
    }
