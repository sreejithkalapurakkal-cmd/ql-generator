import asyncio
import re
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
                    companyName=company.get("company_name") or company.get("organization") or company.get("domain", "Unknown"),
                    domain=company.get("domain", ""),
                    industry=company.get("industry") or "",
                    employeeCount=company.get("employee_count"),
                    estimatedRevenue=company.get("estimated_revenue") or company.get("annual_revenue") or company.get("revenue"),
                    location=company.get("location") or company.get("city") or company.get("country"),
                    description=_clean_description(company.get("description") or company.get("content", "")),
                    techStack=company.get("tech_stack", []),
                    fundingStage=company.get("funding_stage"),
                    linkedinUrl=company.get("linkedin_url"),
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
        ranked = _filter_by_geography(ranked, ctx.icp_profile.geographies)
        ranked = _filter_by_industry(ranked, ctx.icp_profile.industries)
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


def _clean_description(text: str, max_length: int = 300) -> str:
    """Strip markdown/HTML noise from raw page content and truncate."""
    if not text:
        return ""
    # Remove markdown headings, bullets, bold/italic markers
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"\*{1,3}([^*]*)\*{1,3}", r"\1", text)
    # Remove square-bracket navigation artefacts like [Skip to main content]
    text = re.sub(r"\[[^\]]{0,60}\]", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_length:
        text = text[:max_length].rsplit(" ", 1)[0] + "…"
    return text


def _generate_search_queries(icp: ICPProfile) -> list[str]:
    """Generate search queries from ICP profile."""
    queries = []

    industries = icp.industries[:3]
    geos = icp.geographies[:3]
    geo_str = f" in {', '.join(geos)}" if geos else ""
    size_min = icp.company_size_range.get("min", 0)
    size_max = icp.company_size_range.get("max", 0)
    size_str = f" {size_min}-{size_max} employees" if (size_min and size_max) else ""

    for industry in industries:
        queries.append(f"{industry} companies{geo_str}{size_str}")

    # Add tech stack query — always include geography
    if icp.tech_stack:
        tech_query = f"companies using {', '.join(icp.tech_stack[:3])}"
        if industries:
            tech_query += f" in {industries[0]}"
        tech_query += geo_str
        queries.append(tech_query)

    # Add keyword queries — always include geography
    for keyword in icp.keywords[:2]:
        queries.append(f"{keyword} companies {', '.join(industries[:2])}{geo_str}")

    return queries[:5]


_INDUSTRY_SYNONYMS: dict[str, list[str]] = {
    "it": ["information technology", "software", "tech", "technology"],
    "it industry": ["information technology", "software", "tech", "technology"],
    "information technology": ["information technology", "software", "tech", "technology"],
    "software": ["software", "information technology", "tech"],
    "technology": ["technology", "information technology", "software", "tech"],
    "healthcare": ["healthcare", "health care", "medical", "hospital", "pharma"],
    "finance": ["finance", "financial", "banking", "fintech"],
    "ecommerce": ["ecommerce", "e-commerce", "retail"],
    "education": ["education", "edtech", "e-learning"],
    "manufacturing": ["manufacturing", "industrial"],
    "real estate": ["real estate", "property"],
    "media": ["media", "publishing", "entertainment", "news"],
}


def _expand_industry(industry: str) -> list[str]:
    """Return all synonyms for a given ICP industry string."""
    key = industry.lower().strip()
    synonyms = _INDUSTRY_SYNONYMS.get(key, [])
    # Always include the original and each word as a fallback phrase (not single letters)
    result = set(synonyms)
    result.add(key)
    for word in key.split():
        if len(word) > 2:  # skip short abbreviations like 'it', 'ai', '&'
            result.add(word)
    return list(result)


def _filter_by_industry(leads: list[Lead], industries: list[str]) -> list[Lead]:
    """Drop leads whose industry doesn't match any of the ICP industries."""
    if not industries:
        return leads

    # Build the full set of acceptable industry phrases from synonyms
    accepted_phrases: list[str] = []
    for ind in industries:
        accepted_phrases.extend(_expand_industry(ind))

    filtered = []
    for lead in leads:
        lead_industry = (lead.industry or "").lower()
        if not lead_industry:
            # Industry unknown — enrichment failed, keep the lead
            filtered.append(lead)
            continue
        if any(phrase in lead_industry for phrase in accepted_phrases):
            filtered.append(lead)
        else:
            logger.info(
                "lead_filtered_industry",
                company=lead.company_name,
                industry=lead.industry,
                required_industries=industries,
            )
    return filtered


def _filter_by_geography(leads: list[Lead], geographies: list[str]) -> list[Lead]:
    """Drop leads whose location is known AND doesn't match any ICP geography.
    Leads with no location data (enrichment failed) are kept — they were found
    by a geo-targeted search query so they are likely relevant.
    """
    if not geographies:
        return leads

    geo_tokens = {g.lower().strip() for g in geographies}

    filtered = []
    for lead in leads:
        if not lead.location:
            # Location unknown — give benefit of the doubt
            filtered.append(lead)
            continue
        loc = lead.location.lower()
        if any(geo in loc for geo in geo_tokens):
            filtered.append(lead)
        else:
            logger.info(
                "lead_filtered_geography",
                company=lead.company_name,
                location=lead.location,
                required_geographies=geographies,
            )
    return filtered
