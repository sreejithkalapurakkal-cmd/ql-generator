"""Knowledge Base API endpoints."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.company_knowledge_base import CompanyKnowledgeBase
from app.services.company_kb_service import (
    lookup_from_kb,
    search_kb_structured,
    backfill_kb_from_existing_runs,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


@router.get("/companies")
async def list_kb_companies(
    industry: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None),
    min_employees: Optional[int] = Query(None),
    max_employees: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List/search KB records with filters."""
    records = await search_kb_structured(
        db,
        industry=industry,
        country=country,
        min_score=min_score,
        min_employees=min_employees,
        max_employees=max_employees,
        limit=limit,
        offset=offset,
    )

    return {
        "count": len(records),
        "offset": offset,
        "limit": limit,
        "companies": [
            {
                "id": str(r.id),
                "normalized_domain": r.normalized_domain,
                "canonical_name": r.canonical_name,
                "industry": r.industry,
                "sub_industry": r.sub_industry,
                "country": r.country,
                "city": r.city,
                "state_region": r.state_region,
                "employee_count": r.employee_count,
                "revenue_estimate": r.revenue_estimate,
                "best_icp_match_score": r.best_icp_match_score,
                "best_budget_signal_score": r.best_budget_signal_score,
                "best_urgency_signal_score": r.best_urgency_signal_score,
                "best_final_score": r.best_final_score,
                "best_deal_hotness_score": r.best_deal_hotness_score,
                "best_deal_hotness_tier": r.best_deal_hotness_tier,
                "times_discovered": r.times_discovered,
                "last_enriched_at": r.last_enriched_at.isoformat() if r.last_enriched_at else None,
            }
            for r in records
        ],
    }


@router.get("/companies/{domain:path}")
async def get_kb_company(domain: str, db: AsyncSession = Depends(get_db)):
    """Get canonical KB record by domain."""
    record = await lookup_from_kb(domain, db)
    if not record:
        return {"error": f"No KB record found for domain: {domain}"}

    return {
        "id": str(record.id),
        "normalized_domain": record.normalized_domain,
        "canonical_name": record.canonical_name,
        "industry": record.industry,
        "sub_industry": record.sub_industry,
        "country": record.country,
        "city": record.city,
        "state_region": record.state_region,
        "employee_count": record.employee_count,
        "revenue_estimate": record.revenue_estimate,
        "asset_value": record.asset_value,
        "tech_stack_json": record.tech_stack_json,
        "description": record.description,
        "best_icp_match_score": record.best_icp_match_score,
        "best_budget_signal_score": record.best_budget_signal_score,
        "best_urgency_signal_score": record.best_urgency_signal_score,
        "best_final_score": record.best_final_score,
        "best_deal_hotness_score": record.best_deal_hotness_score,
        "best_deal_hotness_tier": record.best_deal_hotness_tier,
        "best_known_contacts": record.best_known_contacts,
        "data_sources": record.data_sources,
        "times_discovered": record.times_discovered,
        "pipeline_run_ids": record.pipeline_run_ids,
        "first_discovered_at": record.first_discovered_at.isoformat() if record.first_discovered_at else None,
        "last_enriched_at": record.last_enriched_at.isoformat() if record.last_enriched_at else None,
    }


@router.get("/stats")
async def get_kb_stats(db: AsyncSession = Depends(get_db)):
    """KB statistics: total records, avg score, industry breakdown."""
    total = await db.execute(
        select(func.count(CompanyKnowledgeBase.id))
    )
    total_count = total.scalar() or 0

    avg_score_result = await db.execute(
        select(func.avg(CompanyKnowledgeBase.best_final_score)).where(
            CompanyKnowledgeBase.best_final_score.isnot(None)
        )
    )
    avg_score = avg_score_result.scalar()

    avg_times = await db.execute(
        select(func.avg(CompanyKnowledgeBase.times_discovered))
    )
    avg_times_discovered = avg_times.scalar()

    industry_result = await db.execute(
        select(
            CompanyKnowledgeBase.industry,
            func.count(CompanyKnowledgeBase.id),
        )
        .where(CompanyKnowledgeBase.industry.isnot(None))
        .group_by(CompanyKnowledgeBase.industry)
        .order_by(func.count(CompanyKnowledgeBase.id).desc())
        .limit(15)
    )
    industry_breakdown = {row[0]: row[1] for row in industry_result.all()}

    country_result = await db.execute(
        select(
            CompanyKnowledgeBase.country,
            func.count(CompanyKnowledgeBase.id),
        )
        .where(CompanyKnowledgeBase.country.isnot(None))
        .group_by(CompanyKnowledgeBase.country)
        .order_by(func.count(CompanyKnowledgeBase.id).desc())
        .limit(15)
    )
    country_breakdown = {row[0]: row[1] for row in country_result.all()}

    return {
        "total_records": total_count,
        "avg_best_final_score": round(avg_score, 1) if avg_score else None,
        "avg_times_discovered": round(avg_times_discovered, 1) if avg_times_discovered else None,
        "industry_breakdown": industry_breakdown,
        "country_breakdown": country_breakdown,
    }


@router.post("/backfill")
async def trigger_backfill(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Trigger one-time backfill of KB from existing pipeline runs.

    Runs in the foreground (blocking) for simplicity.
    For large datasets, consider running as a background task.
    """
    count = await backfill_kb_from_existing_runs(db)
    return {"status": "completed", "companies_processed": count}
