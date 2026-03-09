from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import List, Optional

from app.db.session import get_db
from app.models.company import Company
from app.models.pipeline import PipelineRun
from app.schemas.company import CompanyResponse, BANTScoreResponse, ContactResponse
from app.services.export_service import generate_xlsx, generate_csv

router = APIRouter(prefix="/leads", tags=["Leads"])


@router.get("/{run_id}/companies", response_model=List[CompanyResponse])
async def get_lead_companies(
    run_id: UUID,
    min_bant_score: Optional[int] = Query(None),
    industry_filter: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("bant_score"),
    db: AsyncSession = Depends(get_db),
):
    # Verify run exists
    run_result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = run_result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    query = (
        select(Company)
        .where(Company.pipeline_run_id == run_id)
        .options(selectinload(Company.contacts), selectinload(Company.bant_score))
    )

    if industry_filter:
        query = query.where(Company.industry.ilike(f"%{industry_filter}%"))

    result = await db.execute(query)
    companies = result.scalars().unique().all()

    response = []
    for company in companies:
        bant = None
        if company.bant_score:
            bant = BANTScoreResponse(
                id=company.bant_score.id,
                budget_score=company.bant_score.budget_score,
                budget_reason=company.bant_score.budget_reason,
                budget_sources=company.bant_score.budget_sources,
                authority_score=company.bant_score.authority_score,
                authority_reason=company.bant_score.authority_reason,
                authority_sources=company.bant_score.authority_sources,
                need_score=company.bant_score.need_score,
                need_reason=company.bant_score.need_reason,
                need_sources=company.bant_score.need_sources,
                timing_score=company.bant_score.timing_score,
                timing_reason=company.bant_score.timing_reason,
                timing_sources=company.bant_score.timing_sources,
                total_score=company.bant_score.total_score,
                overall_summary=company.bant_score.overall_summary,
            )

        contacts = [
            ContactResponse(
                id=c.id,
                full_name=c.full_name,
                first_name=c.first_name,
                last_name=c.last_name,
                designation=c.designation,
                role_category=c.role_category,
                email=c.email,
                phone=c.phone,
                linkedin_url=c.linkedin_url,
                city=c.city,
                source=c.source,
                confidence=c.confidence,
                enrichment_status=c.enrichment_status,
            )
            for c in company.contacts
        ]

        comp_resp = CompanyResponse(
            id=company.id,
            name=company.name,
            website=company.website,
            industry=company.industry,
            sub_industry=company.sub_industry,
            city=company.city,
            state_region=company.state_region,
            country=company.country,
            employee_count=company.employee_count,
            revenue_estimate=company.revenue_estimate,
            tech_stack_json=company.tech_stack_json,
            source=company.source,
            qualification=company.qualification,
            icp_match_score=company.icp_match_score,
            match_reasoning=company.match_reasoning,
            contacts=contacts,
            bant_score=bant,
            promoted=company.promoted,
            description=company.description,
            raw_data_json=company.raw_data_json,
            created_at=company.created_at,
        )
        response.append(comp_resp)

    # Filter by BANT score
    if min_bant_score is not None:
        response = [c for c in response if c.bant_score and c.bant_score.total_score and c.bant_score.total_score >= min_bant_score]

    # Sort
    if sort_by == "bant_score":
        response.sort(key=lambda c: (c.bant_score.total_score if c.bant_score and c.bant_score.total_score else 0), reverse=True)
    elif sort_by == "company_name":
        response.sort(key=lambda c: c.name)
    elif sort_by == "qualification":
        tier_order = {
            "verified_match": 0, "potential_match": 1, "weak_match": 2,
            "best_fit": 3, "good_fit": 4, "possible_fit": 5, "qualified": 6,
        }
        response.sort(key=lambda c: (
            tier_order.get(c.qualification or "", 4),
            -(c.bant_score.total_score if c.bant_score and c.bant_score.total_score else 0),
        ))

    return response


@router.get("/{run_id}/export")
async def export_leads(
    run_id: UUID,
    format: str = Query("xlsx"),
    db: AsyncSession = Depends(get_db),
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
