"""Cross-run discovery intelligence service.

Records which queries/tools produced high-scoring companies and provides
intelligence for future runs with similar ICPs. Compounds over time to
improve Stage 1 discovery efficiency.
"""

import logging
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discovery_intelligence import DiscoveryQuery, ToolEffectiveness
from app.models.company import Company
from app.models.pipeline_log import PipelineLog

logger = logging.getLogger(__name__)


async def _extract_query_texts(db: AsyncSession, run_id: UUID) -> dict[str, str]:
    """Extract tool call context/parameters from pipeline logs for each tool."""
    result = await db.execute(
        select(PipelineLog)
        .where(PipelineLog.pipeline_run_id == run_id)
        .where(PipelineLog.event_type == "tool_start")
        .order_by(PipelineLog.sequence_number)
    )
    logs = result.scalars().all()

    tool_queries: dict[str, list[str]] = {}
    for log in logs:
        data = log.event_data or {}
        tool_name = data.get("tool_name", "")
        context = data.get("context", "")
        if tool_name and context:
            tool_queries.setdefault(tool_name, []).append(context[:500])

    # Join all contexts per tool (deduplicated)
    return {
        tool: " | ".join(dict.fromkeys(contexts))[:1000]
        for tool, contexts in tool_queries.items()
    }


async def record_discovery_intelligence(
    db: AsyncSession,
    run_id: UUID,
    icp_config_id: UUID,
    industry: str,
    country: str,
):
    """Record discovery intelligence after a pipeline run completes.

    Analyzes which companies were sourced by which tools and how they
    scored, then records effective queries for future use.

    Call this after Stage 5 (final scoring) completes.
    """
    try:
        # Get all companies from this run with their source info
        result = await db.execute(
            select(Company).where(Company.pipeline_run_id == run_id)
        )
        companies = list(result.scalars().all())

        if not companies:
            return

        # Extract query texts from pipeline logs
        query_texts = await _extract_query_texts(db, run_id)

        # Group companies by source tool
        by_source: dict[str, list[Company]] = {}
        for c in companies:
            source = c.source or "unknown"
            by_source.setdefault(source, []).append(c)

        # Record per-tool effectiveness
        for tool_name, tool_companies in by_source.items():
            total = len(tool_companies)
            passed_s2 = sum(1 for c in tool_companies if c.qualification == "qualified")
            scores = [c.final_score for c in tool_companies if c.final_score is not None]
            avg_score = sum(scores) / len(scores) if scores else 0.0
            effectiveness = (passed_s2 / max(total, 1)) * avg_score

            # Record the discovery query
            dq = DiscoveryQuery(
                pipeline_run_id=run_id,
                icp_config_id=icp_config_id,
                tool_name=tool_name,
                query_text=query_texts.get(tool_name, ""),
                industry=industry,
                country=country,
                companies_found=total,
                companies_passed_stage2=passed_s2,
                avg_final_score=round(avg_score, 1),
                effectiveness_score=round(effectiveness, 1),
            )
            db.add(dq)

            # Update aggregate tool effectiveness
            await _update_tool_effectiveness(
                db, tool_name, industry, country,
                total, passed_s2, avg_score,
            )

        await db.flush()
        logger.info(
            f"Recorded discovery intelligence for run {run_id}: "
            f"{len(by_source)} tools across {len(companies)} companies"
        )

        # Update tool priorities based on accumulated effectiveness data
        await update_tool_priorities(db)

    except Exception as e:
        logger.warning(f"Failed to record discovery intelligence: {e}")


async def _update_tool_effectiveness(
    db: AsyncSession,
    tool_name: str,
    industry: str,
    country: str,
    new_total: int,
    new_passed: int,
    new_avg_score: float,
):
    """Update the aggregate ToolEffectiveness record."""
    result = await db.execute(
        select(ToolEffectiveness).where(
            and_(
                ToolEffectiveness.tool_name == tool_name,
                ToolEffectiveness.industry == industry,
                ToolEffectiveness.country == country,
            )
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Running average
        old_total = existing.total_companies_sourced
        new_combined_total = old_total + new_total
        existing.total_companies_sourced = new_combined_total
        existing.companies_passed_stage2 += new_passed
        existing.total_runs_used += 1
        # Weighted average of scores
        if new_combined_total > 0:
            existing.avg_final_score = round(
                (existing.avg_final_score * old_total + new_avg_score * new_total) / new_combined_total,
                1,
            )
        existing.effectiveness_score = round(
            (existing.companies_passed_stage2 / max(existing.total_companies_sourced, 1))
            * existing.avg_final_score,
            1,
        )
    else:
        effectiveness = (new_passed / max(new_total, 1)) * new_avg_score
        te = ToolEffectiveness(
            tool_name=tool_name,
            industry=industry,
            country=country,
            total_companies_sourced=new_total,
            companies_passed_stage2=new_passed,
            avg_final_score=round(new_avg_score, 1),
            total_runs_used=1,
            effectiveness_score=round(effectiveness, 1),
        )
        db.add(te)


async def record_early_intelligence(
    db: AsyncSession,
    run_id: UUID,
    icp_config_id: UUID,
    industry: str,
    country: str,
):
    """Record discovery intelligence after Stage 2 (firmographic fit) completes.

    Unlike record_discovery_intelligence (called after Stage 5 using final_score),
    this uses icp_match_score and qualification status available after Stage 2.
    This ensures intelligence is available for the NEXT run even if the current
    run doesn't complete all stages.
    """
    try:
        result = await db.execute(
            select(Company).where(Company.pipeline_run_id == run_id)
        )
        companies = list(result.scalars().all())

        if not companies:
            return

        # Extract query texts from pipeline logs
        query_texts = await _extract_query_texts(db, run_id)

        # Group companies by source tool
        by_source: dict[str, list[Company]] = {}
        for c in companies:
            source = c.source or "unknown"
            by_source.setdefault(source, []).append(c)

        for tool_name, tool_companies in by_source.items():
            total = len(tool_companies)
            passed_s2 = sum(1 for c in tool_companies if c.qualification == "qualified")
            # Use icp_match_score (available after Stage 2) instead of final_score
            scores = [c.icp_match_score for c in tool_companies if c.icp_match_score is not None]
            avg_score = sum(scores) / len(scores) if scores else 0.0
            effectiveness = (passed_s2 / max(total, 1)) * avg_score

            dq = DiscoveryQuery(
                pipeline_run_id=run_id,
                icp_config_id=icp_config_id,
                tool_name=tool_name,
                query_text=query_texts.get(tool_name, ""),
                industry=industry,
                country=country,
                companies_found=total,
                companies_passed_stage2=passed_s2,
                avg_final_score=round(avg_score, 1),
                effectiveness_score=round(effectiveness, 1),
            )
            db.add(dq)

            await _update_tool_effectiveness(
                db, tool_name, industry, country,
                total, passed_s2, avg_score,
            )

        await db.flush()
        logger.info(
            f"Recorded early intelligence (post-Stage 2) for run {run_id}: "
            f"{len(by_source)} tools across {len(companies)} companies"
        )

    except Exception as e:
        logger.warning(f"Failed to record early intelligence: {e}")


async def get_intelligence_for_icp(
    db: AsyncSession,
    industry: str,
    country: str,
    limit: int = 10,
) -> dict:
    """Get discovery intelligence for a given ICP's industry/geography.

    Returns recommended tools and their historical effectiveness,
    plus any proven high-yield queries from past runs.
    """
    try:
        # Get tool effectiveness rankings
        result = await db.execute(
            select(ToolEffectiveness)
            .where(
                and_(
                    ToolEffectiveness.industry == industry,
                    ToolEffectiveness.country == country,
                    ToolEffectiveness.total_companies_sourced >= 3,  # Min sample
                )
            )
            .order_by(ToolEffectiveness.effectiveness_score.desc())
            .limit(limit)
        )
        tool_rankings = [
            {
                "tool_name": te.tool_name,
                "effectiveness_score": te.effectiveness_score,
                "total_sourced": te.total_companies_sourced,
                "pass_rate": round(te.companies_passed_stage2 / max(te.total_companies_sourced, 1) * 100, 1),
                "avg_score": te.avg_final_score,
                "runs_used": te.total_runs_used,
            }
            for te in result.scalars().all()
        ]

        # Get top performing queries from past runs
        result = await db.execute(
            select(DiscoveryQuery)
            .where(
                and_(
                    DiscoveryQuery.industry == industry,
                    DiscoveryQuery.country == country,
                    DiscoveryQuery.effectiveness_score > 0,
                )
            )
            .order_by(DiscoveryQuery.effectiveness_score.desc())
            .limit(5)
        )
        top_queries = [
            {
                "tool_name": dq.tool_name,
                "query_text": dq.query_text,
                "effectiveness": dq.effectiveness_score,
                "companies_found": dq.companies_found,
                "pass_rate": round(dq.companies_passed_stage2 / max(dq.companies_found, 1) * 100, 1),
            }
            for dq in result.scalars().all()
        ]

        return {
            "has_intelligence": bool(tool_rankings or top_queries),
            "tool_rankings": tool_rankings,
            "top_queries": top_queries,
            "industry": industry,
            "country": country,
        }

    except Exception as e:
        logger.warning(f"Failed to get discovery intelligence: {e}")
        return {
            "has_intelligence": False,
            "tool_rankings": [],
            "top_queries": [],
        }


def format_intelligence_for_prompt(intelligence: dict) -> str:
    """Format intelligence data for inclusion in agent prompts.

    Returns a human-readable section that can be injected into
    the Stage 1 discovery prompt.
    """
    if not intelligence.get("has_intelligence"):
        return ""

    lines = ["\n═══════════════════════════════════════════"]
    lines.append("INTELLIGENCE FROM PREVIOUS RUNS")
    lines.append("═══════════════════════════════════════════")

    rankings = intelligence.get("tool_rankings", [])
    if rankings:
        lines.append("\nTool effectiveness (best sources for this industry/geography):")
        for r in rankings[:5]:
            lines.append(
                f"  {r['tool_name']}: effectiveness={r['effectiveness_score']:.0f}, "
                f"pass_rate={r['pass_rate']:.0f}%, avg_score={r['avg_score']:.0f}, "
                f"used in {r['runs_used']} runs"
            )
        lines.append("Prioritize tools with higher effectiveness scores.")

    top_queries = intelligence.get("top_queries", [])
    if top_queries:
        lines.append("\nHigh-yield queries from past runs:")
        for q in top_queries[:3]:
            if q.get("query_text"):
                lines.append(
                    f"  [{q['tool_name']}] \"{q['query_text']}\" "
                    f"(found {q['companies_found']}, {q['pass_rate']:.0f}% passed)"
                )

    return "\n".join(lines)


async def update_tool_priorities(db: AsyncSession):
    """Update tool registry priorities based on aggregate effectiveness data.

    Tools with enough data (>=5 effectiveness records across runs) will have
    their priority score updated. Tools that fall below their effectiveness
    threshold will be auto-disabled.
    """
    from app.models.tool_registry import ToolRegistry

    try:
        result = await db.execute(
            select(ToolEffectiveness)
            .where(ToolEffectiveness.total_runs_used >= 3)
        )
        effectiveness_records = result.scalars().all()

        # Aggregate by tool_name across all industries/countries
        tool_scores: dict[str, list[float]] = {}
        for te in effectiveness_records:
            tool_scores.setdefault(te.tool_name, []).append(te.effectiveness_score)

        for tool_name, scores in tool_scores.items():
            avg_effectiveness = sum(scores) / len(scores) if scores else 0
            priority = min(100, max(0, int(avg_effectiveness)))

            tool_result = await db.execute(
                select(ToolRegistry).where(ToolRegistry.tool_name == tool_name)
            )
            tool = tool_result.scalar_one_or_none()
            if tool:
                tool.priority = priority
                threshold = tool.effectiveness_threshold or 20.0
                if avg_effectiveness < threshold and len(scores) >= 5:
                    tool.auto_disabled = True
                    logger.info(
                        f"Auto-disabled {tool_name}: avg effectiveness {avg_effectiveness:.1f} "
                        f"below threshold {threshold}"
                    )
                elif tool.auto_disabled and avg_effectiveness >= threshold:
                    tool.auto_disabled = False

        await db.flush()
        logger.info(f"Updated priorities for {len(tool_scores)} tools")

    except Exception as e:
        logger.warning(f"Failed to update tool priorities: {e}")
