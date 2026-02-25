import asyncio
from datetime import datetime, timezone

import structlog
from fastapi import BackgroundTasks, FastAPI, HTTPException

from agent.core import (
    PipelineContext,
    enrich_companies,
    search_with_fallback,
)
from agent.tools.company_scorer import bant_score
from config import settings
from models import BANTScore, ICPProfile, JobRequest, Lead
from services.callback_client import send_callback
from services.progress_reporter import report_progress

logger = structlog.get_logger()

app = FastAPI(title="qlGen Agent", version="0.1.0")


@app.get("/health")
async def health():
    return {
        "status": "UP",
        "service": "qlgen-agent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/v1/process")
async def process_job(request: JobRequest, background_tasks: BackgroundTasks):
    """Accept a job and process it asynchronously."""
    logger.info("job_received", job_id=request.job_id)
    background_tasks.add_task(run_agent_pipeline, request)
    return {"status": "accepted", "jobId": request.job_id}


async def run_agent_pipeline(request: JobRequest) -> None:
    """Execute the full agent pipeline: search -> enrich -> score -> rank."""
    ctx = PipelineContext(
        job_id=request.job_id,
        icp_profile=request.icp_profile,
        bant_weights=request.bant_weights,
        max_results=request.max_results,
        callback_url=request.callback_url,
    )

    try:
        # Stage 1: Generate search queries from ICP
        await report_progress(ctx.job_id, "SEARCHING", "Interpreting ICP and generating queries...", 5)

        search_queries = _generate_search_queries(ctx.icp_profile)
        ctx.search_queries = search_queries
        logger.info("queries_generated", job_id=ctx.job_id, count=len(search_queries))

        # Stage 2: Discover companies
        await report_progress(ctx.job_id, "SEARCHING", "Discovering companies...", 15)

        for i, query in enumerate(search_queries):
            results = await search_with_fallback(query, max_results=15)
            for result in results:
                ctx.add_company(result)
            progress = 15 + int((i + 1) / len(search_queries) * 25)
            await report_progress(
                ctx.job_id, "SEARCHING",
                f"Search query {i + 1}/{len(search_queries)} complete ({len(ctx.raw_companies)} companies found)",
                progress,
            )

        logger.info("discovery_complete", job_id=ctx.job_id, companies=len(ctx.raw_companies))

        if not ctx.raw_companies:
            await report_progress(ctx.job_id, "COMPLETED", "No companies found matching ICP", 100)
            await send_callback(ctx.callback_url, ctx.job_id, "COMPLETED", leads=[])
            return

        # Stage 3: Enrich companies
        await report_progress(
            ctx.job_id, "ENRICHING",
            f"Enriching {len(ctx.raw_companies)} companies...", 40,
        )

        enriched = await enrich_companies(
            ctx.raw_companies[:ctx.max_results * 2],  # Enrich more than needed
            max_concurrent=settings.max_enrichment_concurrent,
        )
        ctx.enriched_companies = enriched

        logger.info("enrichment_complete", job_id=ctx.job_id, enriched=len(enriched))
        await report_progress(
            ctx.job_id, "ENRICHING",
            f"Enriched {len(enriched)} companies", 65,
        )

        # Stage 4: BANT Scoring
        await report_progress(ctx.job_id, "SCORING", "Applying BANT scoring...", 70)

        icp_dict = ctx.icp_profile.model_dump(by_alias=True)
        bant_dict = ctx.bant_weights.model_dump()

        scored_leads: list[Lead] = []
        for i, company in enumerate(enriched):
            try:
                score_result = bant_score(
                    company_profile=company,
                    icp_profile=icp_dict,
                    bant_weights=bant_dict,
                )

                lead = Lead(
                    companyName=company.get("company_name") or company.get("title", "Unknown"),
                    domain=company.get("domain", ""),
                    industry=company.get("industry", ""),
                    employeeCount=company.get("employee_count"),
                    estimatedRevenue=company.get("estimated_revenue") or company.get("annual_revenue") or company.get("revenue"),
                    location=company.get("location"),
                    description=company.get("description") or company.get("content", ""),
                    techStack=company.get("tech_stack", []),
                    fundingStage=company.get("funding_stage"),
                    bantScore=BANTScore(
                        budget=score_result["budget"],
                        authority=score_result["authority"],
                        need=score_result["need"],
                        timeline=score_result["timeline"],
                        total=score_result["total"],
                        reasoning=score_result["reasoning"],
                    ),
                )
                scored_leads.append(lead)
            except Exception as e:
                logger.warning("scoring_failed", company=company.get("domain"), error=str(e))

            if (i + 1) % 5 == 0:
                progress = 70 + int((i + 1) / len(enriched) * 25)
                await report_progress(
                    ctx.job_id, "SCORING",
                    f"Scored {i + 1}/{len(enriched)} companies", progress,
                )

        # Stage 5: Rank and return
        ranked = sorted(scored_leads, key=lambda l: l.bant_score.total, reverse=True)
        ranked = ranked[: ctx.max_results]
        ctx.scored_leads = ranked

        logger.info("pipeline_complete", job_id=ctx.job_id, leads=len(ranked))
        await report_progress(
            ctx.job_id, "COMPLETED",
            f"Found {len(ranked)} qualified leads", 100,
        )
        await send_callback(ctx.callback_url, ctx.job_id, "COMPLETED", leads=ranked)

    except Exception as e:
        logger.error("pipeline_failed", job_id=ctx.job_id, error=str(e))
        try:
            await send_callback(ctx.callback_url, ctx.job_id, "FAILED", error=str(e))
        except Exception:
            logger.error("failed_to_send_failure_callback", job_id=ctx.job_id)


def _generate_search_queries(icp: ICPProfile) -> list[str]:
    """Generate search queries from ICP profile."""
    queries = []

    industries = icp.industries[:3]
    geos = icp.geographies[:3]
    size_min = icp.company_size_range.get("min", 0)
    size_max = icp.company_size_range.get("max", 0)

    for industry in industries:
        base_query = f"{industry} companies"

        if geos:
            base_query += f" in {', '.join(geos)}"

        if size_min and size_max:
            base_query += f" {size_min}-{size_max} employees"

        queries.append(base_query)

    # Add tech stack query
    if icp.tech_stack:
        tech_query = f"companies using {', '.join(icp.tech_stack[:3])}"
        if industries:
            tech_query += f" in {industries[0]}"
        queries.append(tech_query)

    # Add keyword queries
    for keyword in icp.keywords[:2]:
        queries.append(f"{keyword} companies {', '.join(industries[:2])}")

    return queries[:5]
