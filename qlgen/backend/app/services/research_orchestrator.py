"""Research Orchestrator Service.

Coordinates multi-stage research jobs: plans research strategy,
executes specialist agents (parallel where possible), synthesizes
findings, generates briefs, and tracks progress via SSE events.
"""
import asyncio
import logging
import uuid as uuid_mod
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.models.research_job import ResearchJob
from app.models.company_knowledge_base import CompanyKnowledgeBase
from app.models.activity_event import ActivityEvent
from app.services import event_store
from app.events.event_bus import bus, Events

logger = logging.getLogger(__name__)

# Research stages and their weights for progress calculation
STAGES = [
    {"id": "planning", "label": "Planning research strategy", "weight": 5},
    {"id": "signal_discovery", "label": "Discovering signals", "weight": 25},
    {"id": "hiring_intel", "label": "Analyzing hiring patterns", "weight": 15},
    {"id": "executive_intel", "label": "Tracking executive changes", "weight": 15},
    {"id": "competitive_intel", "label": "Mapping competitive landscape", "weight": 15},
    {"id": "tech_stack_intel", "label": "Detecting technology stack", "weight": 10},
    {"id": "procurement_intel", "label": "Scanning procurement activity", "weight": 10},
    {"id": "confidence_check", "label": "Verifying signal confidence", "weight": 5},
    {"id": "synthesis", "label": "Synthesizing research brief", "weight": 10},
]

# Parallel execution groups by research depth
PARALLEL_GROUPS = {
    "standard": [
        ["signal_discovery", "hiring_intel", "executive_intel"],  # Group 1: run in parallel
        ["confidence_check"],  # Group 2: needs Group 1 results
        ["synthesis"],  # Group 3: needs everything
    ],
    "deep": [
        ["signal_discovery", "hiring_intel", "executive_intel"],
        ["competitive_intel", "tech_stack_intel"],
        ["confidence_check"],
        ["synthesis"],
    ],
    "comprehensive": [
        ["signal_discovery", "hiring_intel", "executive_intel"],
        ["competitive_intel", "tech_stack_intel", "procurement_intel"],
        ["confidence_check"],
        ["synthesis"],
    ],
}


async def create_research_job(
    db: AsyncSession,
    company_kb_id: UUID,
    user_id: UUID,
    job_type: str = "full_research",
    research_depth: str = "standard",
    config: dict | None = None,
) -> ResearchJob:
    """Create a new research job record."""
    job = ResearchJob(
        company_kb_id=company_kb_id,
        user_id=user_id,
        job_type=job_type,
        research_depth=research_depth,
        config=config or {},
        status="pending",
    )
    db.add(job)
    await db.flush()
    return job


async def execute_research_job(job_id: UUID) -> None:
    """Background task: execute a full research job.

    Opens its own DB session. Emits SSE events for real-time progress.
    Coordinates specialist stages sequentially and in parallel groups.
    """
    run_id = str(job_id)

    async with async_session() as db:
        try:
            # Load job
            result = await db.execute(
                select(ResearchJob).where(ResearchJob.id == job_id)
            )
            job = result.scalar_one_or_none()
            if not job:
                logger.error(f"ResearchJob {job_id} not found")
                return

            # Load company
            kb_result = await db.execute(
                select(CompanyKnowledgeBase).where(
                    CompanyKnowledgeBase.id == job.company_kb_id
                )
            )
            kb = kb_result.scalar_one_or_none()
            if not kb:
                job.status = "failed"
                job.error = "Company not found"
                await db.commit()
                return

            company_name = kb.canonical_name or kb.normalized_domain or "Unknown"
            domain = kb.normalized_domain or ""

            # Mark running
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            await db.commit()

            await event_store.push_event(run_id, {
                "type": "research_started",
                "data": {
                    "company_name": company_name,
                    "job_type": job.job_type,
                    "depth": job.research_depth,
                },
            })

            # Emit event bus event for cross-service reactions
            await bus.emit(Events.RESEARCH_STARTED, {
                "job_id": str(job_id),
                "company_kb_id": str(job.company_kb_id),
                "company_name": company_name,
            })

            # Create milestone activity event
            db.add(ActivityEvent(
                research_job_id=job_id,
                company_kb_id=job.company_kb_id,
                event_type="research_start",
                event_category="research",
                narrative=f"Starting {job.research_depth} research for {company_name}",
                milestone=True,
                verbosity_level="summary",
            ))
            await db.flush()

            config = job.config or {}
            total_weight = sum(s["weight"] for s in STAGES)
            completed_weight = 0
            total_signals = 0
            total_tool_calls = 0

            # ── Stage 1: Planning ──
            stage = STAGES[0]
            await _emit_stage(run_id, stage, completed_weight, total_weight)
            job.current_stage = stage["id"]

            # For planning, we determine which stages to run
            stages_to_run = _plan_stages(job.job_type, job.research_depth, config)

            db.add(ActivityEvent(
                research_job_id=job_id,
                company_kb_id=job.company_kb_id,
                event_type="tool_call",
                event_category="research",
                narrative=f"Research plan: {len(stages_to_run)} stages for {company_name}",
                narrative_detail=f"Stages: {', '.join(s['label'] for s in stages_to_run)}",
                verbosity_level="detailed",
            ))

            completed_weight += stage["weight"]
            await db.flush()

            # ── Execute research stages in parallel groups ──
            depth = job.research_depth or "standard"
            groups = PARALLEL_GROUPS.get(depth, PARALLEL_GROUPS["standard"])

            for group in groups:
                if await event_store.is_cancelled(run_id):
                    job.status = "cancelled"
                    job.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                    return

                # Filter to only stages that are in stages_to_run
                group_stages = [s for s in stages_to_run if s["id"] in group]
                if not group_stages:
                    continue

                # Emit stage_started for each stage in the group
                for stage in group_stages:
                    await _emit_stage(run_id, stage, completed_weight, total_weight)

                # Execute group stages in parallel
                async def run_stage(stg):
                    try:
                        return stg["id"], await _execute_stage(db, job, kb, company_name, domain, stg, config)
                    except Exception as e:
                        logger.warning(f"Stage {stg['id']} failed: {e}")
                        return stg["id"], {"error": str(e)[:500], "signals_found": 0, "tool_calls": 0}

                if len(group_stages) > 1:
                    # Run in parallel
                    results = await asyncio.gather(
                        *[run_stage(s) for s in group_stages],
                        return_exceptions=False,
                    )
                else:
                    # Single stage, run directly
                    results = [await run_stage(group_stages[0])]

                # Process results
                for stage_id, stage_result in results:
                    stage = next((s for s in group_stages if s["id"] == stage_id), None)
                    if not stage:
                        continue

                    signals_found = stage_result.get("signals_found", 0)
                    tool_calls = stage_result.get("tool_calls", 0)
                    total_signals += signals_found
                    total_tool_calls += tool_calls

                    if "error" in stage_result:
                        db.add(ActivityEvent(
                            research_job_id=job_id,
                            company_kb_id=job.company_kb_id,
                            event_type="error",
                            event_category="research",
                            narrative=f"{stage['label']} encountered an error",
                            technical_detail=stage_result,
                            verbosity_level="technical",
                        ))
                    else:
                        db.add(ActivityEvent(
                            research_job_id=job_id,
                            company_kb_id=job.company_kb_id,
                            event_type="tool_call",
                            event_category="research",
                            narrative=f"{stage['label']}: {signals_found} signals found",
                            technical_detail=stage_result,
                            verbosity_level="detailed",
                        ))

                    completed_weight += stage["weight"]

                job.progress = {
                    "percent": round((completed_weight / total_weight) * 100),
                    "current_stage": group_stages[-1]["id"],
                    "label": f"Completed: {', '.join(s['label'] for s in group_stages)}",
                }
                job.signals_detected = total_signals
                job.total_tool_calls = total_tool_calls
                await db.flush()

            # ── Complete ──
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.signals_detected = total_signals
            job.total_tool_calls = total_tool_calls

            db.add(ActivityEvent(
                research_job_id=job_id,
                company_kb_id=job.company_kb_id,
                event_type="research_complete",
                event_category="research",
                narrative=f"Research complete for {company_name}: {total_signals} signals detected",
                milestone=True,
                verbosity_level="summary",
            ))

            await db.commit()

            await event_store.push_event(run_id, {
                "type": "research_completed",
                "data": {
                    "signals_detected": total_signals,
                    "tool_calls": total_tool_calls,
                    "company_name": company_name,
                },
            })

            # Emit event bus event
            await bus.emit(Events.RESEARCH_COMPLETED, {
                "job_id": str(job_id),
                "company_kb_id": str(job.company_kb_id),
                "signals_detected": total_signals,
            })

        except Exception as e:
            logger.error(f"Research job {job_id} failed: {e}", exc_info=True)
            try:
                async with async_session() as err_db:
                    result = await err_db.execute(
                        select(ResearchJob).where(ResearchJob.id == job_id)
                    )
                    j = result.scalar_one_or_none()
                    if j:
                        j.status = "failed"
                        j.error = str(e)[:2000]
                        j.completed_at = datetime.now(timezone.utc)
                        await err_db.commit()
                await event_store.push_event(run_id, {
                    "type": "research_failed",
                    "data": {"message": str(e)[:500]},
                })
                await bus.emit(Events.RESEARCH_FAILED, {
                    "job_id": str(job_id),
                    "error": str(e)[:500],
                })
            except Exception:
                logger.error(f"Failed to update job {job_id} status", exc_info=True)


def _plan_stages(job_type: str, depth: str, config: dict) -> list[dict]:
    """Determine which research stages to run based on job type and depth."""
    if job_type == "signal_scan":
        return [s for s in STAGES if s["id"] in ("signal_discovery",)]
    if job_type == "contact_enrichment":
        return [s for s in STAGES if s["id"] in ("executive_intel",)]
    if job_type == "brief_generation":
        return [s for s in STAGES if s["id"] in ("synthesis",)]

    # full_research
    if depth == "standard":
        return [s for s in STAGES if s["id"] not in ("planning", "competitive_intel", "tech_stack_intel")]
    if depth == "deep":
        return [s for s in STAGES if s["id"] != "planning"]
    # comprehensive
    return [s for s in STAGES if s["id"] != "planning"]


async def _execute_stage(
    db: AsyncSession,
    job: ResearchJob,
    kb: CompanyKnowledgeBase,
    company_name: str,
    domain: str,
    stage: dict,
    config: dict,
) -> dict:
    """Execute a single research stage. Returns stage result dict."""
    stage_id = stage["id"]

    if stage_id == "signal_discovery":
        from app.services.signal_service import detect_signals_for_company
        signals = await detect_signals_for_company(
            db, job.company_kb_id,
            signal_hints=config.get("signal_hints"),
        )
        return {"signals_found": len(signals), "tool_calls": 6}

    elif stage_id == "hiring_intel":
        from app.services.signal_service import detect_signals_for_company
        signals = await detect_signals_for_company(
            db, job.company_kb_id,
            signal_types=["hiring_surge"],
        )
        return {"signals_found": len(signals), "tool_calls": 2}

    elif stage_id == "executive_intel":
        from app.services.signal_service import detect_signals_for_company
        signals = await detect_signals_for_company(
            db, job.company_kb_id,
            signal_types=["executive_change", "champion_job_change"],
        )
        return {"signals_found": len(signals), "tool_calls": 2}

    elif stage_id == "competitive_intel":
        from app.services.signal_service import detect_signals_for_company
        signals = await detect_signals_for_company(
            db, job.company_kb_id,
            signal_types=["competitor_adoption", "competitor_churn", "partnership"],
        )
        return {"signals_found": len(signals), "tool_calls": 3}

    elif stage_id == "tech_stack_intel":
        from app.services.signal_service import detect_signals_for_company
        signals = await detect_signals_for_company(
            db, job.company_kb_id,
            signal_types=["tech_adoption"],
        )
        return {"signals_found": len(signals), "tool_calls": 1}

    elif stage_id == "procurement_intel":
        from app.tools.procurement_intel_tool import scan_procurement_activity
        result = await asyncio.to_thread(
            scan_procurement_activity, kb_name, kb_domain,
        )
        signals_found = result.get("total_found", 0)
        if signals_found > 0:
            from app.services.signal_service import save_signals_from_raw
            saved = await save_signals_from_raw(
                db, job.company_kb_id,
                signal_type="procurement_activity",
                raw_signals=[{
                    "title": s.get("title", "Procurement activity detected"),
                    "summary": s.get("description"),
                    "source_url": s.get("source_url"),
                    "source_class": "procurement",
                    "strength": result.get("signal_strength", 50),
                    "priority": "medium",
                } for s in result.get("procurement_signals", [])[:5]],
            )
            signals_found = len(saved) if saved else 0
        return {"signals_found": signals_found, "tool_calls": 1}

    elif stage_id == "confidence_check":
        from app.services.confidence_scorer import score_company_signals
        scored = await score_company_signals(db, job.company_kb_id)

        # For deep/comprehensive depth, use LLM verification agent on medium-confidence signals
        verified_count = 0
        if job.research_depth in ("deep", "comprehensive"):
            try:
                from app.models.signal_event import SignalEvent
                medium_signals = (await db.execute(
                    select(SignalEvent).where(
                        SignalEvent.company_kb_id == job.company_kb_id,
                        SignalEvent.confidence == "medium",
                        SignalEvent.is_dismissed == False,
                    ).limit(5)
                )).scalars().all()

                if medium_signals:
                    from app.agent.confidence_verification_agent import create_confidence_verification_agent
                    agent = create_confidence_verification_agent()

                    async def _verify(signal):
                        prompt = (
                            f"Verify this signal for {kb_name}:\n"
                            f"Title: {signal.title}\n"
                            f"Summary: {signal.summary or 'N/A'}\n"
                            f"Source: {signal.source_url or 'N/A'}\n"
                            f"Return JSON with verified, adjusted_confidence, and reasoning."
                        )
                        return await asyncio.to_thread(agent, prompt)

                    results = await asyncio.gather(
                        *(_verify(s) for s in medium_signals),
                        return_exceptions=True,
                    )
                    for signal, result in zip(medium_signals, results):
                        if isinstance(result, Exception):
                            logger.warning(f"Confidence verification failed for signal {signal.id}: {result}")
                        else:
                            verified_count += 1
            except Exception as e:
                logger.warning(f"Confidence verification stage failed: {e}")

        return {"signals_scored": scored, "signals_verified": verified_count, "tool_calls": verified_count}

    elif stage_id == "synthesis":
        from app.services.brief_service import generate_structured_brief
        brief = await generate_structured_brief(db, job.company_kb_id)
        job.brief_version = brief.get("version") if isinstance(brief, dict) else None
        return {"brief_generated": True, "tool_calls": 1}

    return {"skipped": True, "tool_calls": 0}


async def _emit_stage(run_id: str, stage: dict, completed: float, total: float):
    """Emit SSE progress event for a stage."""
    await event_store.push_event(run_id, {
        "type": "stage_started",
        "data": {
            "stage_id": stage["id"],
            "label": stage["label"],
            "percent": round((completed / total) * 100),
        },
    })
