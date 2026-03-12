"""5-stage pipeline orchestration with mandatory user review gates.

Stage 1: Industry Discovery (automatic)
Stage 2: Firmographic Fit Check (automatic → pause for review)
Stage 3: Budget & Urgency Signals (flexible: serial or parallel → pause)
Stage 4: Contact Discovery (automatic)
Stage 5: Final Scoring & Ranking (computation)
"""
import asyncio
import json
import logging
import traceback
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import select, func

from app.agent.lead_gen_agent import (
    create_industry_discovery_agent,
    create_firmographic_fit_agent,
    create_signal_agent,
    create_contact_agent,
    create_pipeline_callback_handler,
    compute_final_score,
    PipelineCancelled,
)
from app.agent.prompt_builder import (
    build_industry_discovery_prompt,
    build_firmographic_fit_prompt,
    build_signal_prompt,
    build_contact_discovery_prompt,
)
from app.db.session import async_session
from app.models.pipeline import PipelineRun
from app.models.icp import ICPConfig
from app.models.company import Company
from app.models.contact import Contact
from app.models.company_stage import CompanyStageResult
from app.models.pipeline_log import PipelineLog
from app.services.tool_registry_service import get_disabled_tool_names

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# Utility functions
# ──────────────────────────────────────────────────────────────────

def _emit_event(events: dict, run_id: str, event: dict):
    """Add event to the SSE event list."""
    if events is not None and run_id in events:
        events[run_id].append(event)


def _repair_truncated_json(text: str) -> str:
    """Attempt to repair truncated JSON by closing open strings, arrays, and objects."""
    in_string = False
    escape_next = False
    stack = []

    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in ('{', '['):
            stack.append(ch)
        elif ch == '}' and stack and stack[-1] == '{':
            stack.pop()
        elif ch == ']' and stack and stack[-1] == '[':
            stack.pop()

    repaired = text
    if in_string:
        repaired += '"'
    for bracket in reversed(stack):
        repaired += '}' if bracket == '{' else ']'

    return repaired


def _truncate_to_last_complete_item(text: str) -> str:
    """Cut JSON text back to the last cleanly-closed array element."""
    last_obj_end = -1
    for marker in ['},\n', '},\r', '}, ']:
        pos = text.rfind(marker)
        if pos > last_obj_end:
            last_obj_end = pos

    if last_obj_end > 0:
        return text[: last_obj_end + 1]
    return text


def parse_json_from_agent_result(result) -> dict:
    """Extract JSON from the agent's text response, repairing truncation if needed."""
    text = str(result)

    if "```json" in text:
        start = text.index("```json") + 7
        closing = text.find("```", start)
        text = text[start:closing].strip() if closing != -1 else text[start:].strip()
    elif "```" in text:
        start = text.index("```") + 3
        closing = text.find("```", start)
        text = text[start:closing].strip() if closing != -1 else text[start:].strip()

    if "{" in text:
        start = text.index("{")
        depth = 0
        end = len(text)
        for i, char in enumerate(text[start:], start):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        text = text[start:end]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    try:
        repaired = _repair_truncated_json(text)
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    try:
        truncated = _truncate_to_last_complete_item(text)
        repaired = _repair_truncated_json(truncated)
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    logger.error(f"Failed to parse agent JSON (length={len(text)}). First 500 chars: {text[:500]}")
    return json.loads(text)


def _normalize_score_to_100(score: float | None) -> float | None:
    """Normalize a score to the 0-100 range.

    If the LLM returns a score on a 0-10 scale, multiply by 10.
    Clamp to [0, 100].
    """
    if score is None:
        return None
    score = float(score)
    if score <= 10:
        score = score * 10
    return min(100.0, max(0.0, score))


def _chunk(lst, size):
    """Split a list into chunks of given size."""
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


# ──────────────────────────────────────────────────────────────────
# Data reuse / caching
# ──────────────────────────────────────────────────────────────────

async def find_cached_company(domain: str, db) -> Company | None:
    """Find the most recent, most enriched version of a company by domain."""
    domain_clean = domain.lower().strip().removeprefix("www.").removeprefix("http://").removeprefix("https://").rstrip("/")
    if not domain_clean:
        return None

    result = await db.execute(
        select(Company)
        .where(func.lower(Company.website).contains(domain_clean))
        .where(Company.final_score.isnot(None))
        .order_by(Company.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def clone_company_data(cached: Company, new_company: Company):
    """Copy enriched data from a cached company to a new one."""
    if cached.employee_count and not new_company.employee_count:
        new_company.employee_count = cached.employee_count
    if cached.revenue_estimate and not new_company.revenue_estimate:
        new_company.revenue_estimate = cached.revenue_estimate
    if cached.tech_stack_json and not new_company.tech_stack_json:
        new_company.tech_stack_json = cached.tech_stack_json
    if cached.description and not new_company.description:
        new_company.description = cached.description
    if cached.embedding is not None and new_company.embedding is None:
        new_company.embedding = cached.embedding

    new_company.cached_from_run_id = cached.pipeline_run_id
    new_company.data_freshness = cached.data_freshness or cached.created_at


# ──────────────────────────────────────────────────────────────────
# Firmographic pre-filter (computational — no agent)
# ──────────────────────────────────────────────────────────────────

def quick_firmographic_filter(companies: list[Company], icp: dict) -> tuple[list, list, list]:
    """Fast filter using data already available from Stage 1.

    Returns (passed, failed_with_reasons, needs_agent).
    Uses generous margins to avoid wrongly excluding.
    """
    fd = icp.get("firmographic_details", {})
    emp_range = fd.get("employee_range", {})
    rev_range = fd.get("revenue_range", {})

    emp_min = emp_range.get("min")
    emp_max = emp_range.get("max")
    rev_min = rev_range.get("min")
    rev_max = rev_range.get("max")

    passed = []
    failed = []
    needs_agent = []

    for c in companies:
        emp = c.employee_count
        rev = c.revenue_estimate

        # If employee count known and clearly outside range (generous margins)
        if emp and emp_min and emp_max:
            if emp < emp_min * 0.5 or emp > emp_max * 2:
                failed.append((c, f"Employee count {emp} outside range {emp_min}-{emp_max} (with 0.5x-2x margin)"))
                continue

        # If revenue known and clearly outside range
        if rev and rev_min and rev_max:
            if rev < rev_min * 0.3 or rev > rev_max * 3:
                failed.append((c, f"Revenue ${rev:,} outside range ${rev_min:,}-${rev_max:,} (with 0.3x-3x margin)"))
                continue

        # If both known and within generous range → pass to agent for deep check
        if emp and rev:
            passed.append(c)
        else:
            needs_agent.append(c)

    return passed, failed, needs_agent


# ──────────────────────────────────────────────────────────────────
# Shared error handling wrapper
# ──────────────────────────────────────────────────────────────────

async def _handle_pipeline_error(db, run_id, run, event_collector, events, run_id_str, error, cancelled=False):
    """Shared error handling for pipeline execution failures."""
    try:
        await db.rollback()
    except Exception:
        pass

    try:
        result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
        run = result.scalar_one_or_none()
        if run:
            if cancelled:
                run.status = "cancelled"
            else:
                run.status = "failed"
                run.error_log = f"{str(error)}\n{traceback.format_exc()}"
            run.completed_at = datetime.now(timezone.utc)

            for seq, event_data in enumerate(event_collector):
                log = PipelineLog(
                    pipeline_run_id=run_id,
                    event_type=event_data.get("type", "unknown"),
                    event_data=event_data,
                    sequence_number=seq,
                )
                db.add(log)
            await db.commit()
    except Exception as commit_err:
        logger.error(f"Failed to persist {'cancelled' if cancelled else 'error'} status for pipeline {run_id}: {commit_err}")

    if cancelled:
        _emit_event(events, run_id_str, {
            "type": "cancelled",
            "companies_found": run.companies_found or 0 if run else 0,
            "contacts_found": run.contacts_found or 0 if run else 0,
        })
    else:
        _emit_event(events, run_id_str, {
            "type": "error",
            "message": str(error),
        })


async def _persist_logs(db, run_id, event_collector, offset=0):
    """Persist event_collector to PipelineLog table."""
    for seq, event_data in enumerate(event_collector):
        log = PipelineLog(
            pipeline_run_id=run_id,
            event_type=event_data.get("type", "unknown"),
            event_data=event_data,
            sequence_number=offset + seq,
        )
        db.add(log)


async def _get_existing_log_count(db, run_id) -> int:
    """Count existing pipeline logs for sequence offset."""
    result = await db.execute(
        select(func.count(PipelineLog.id)).where(PipelineLog.pipeline_run_id == run_id)
    )
    return result.scalar() or 0


# ──────────────────────────────────────────────────────────────────
# Main pipeline: Stages 1 + 2 → pause for review
# ──────────────────────────────────────────────────────────────────

async def execute_pipeline(run_id: UUID, events: dict = None, cancelled_runs: set = None):
    """Execute Stages 1 (Industry Discovery) and 2 (Firmographic Fit).

    After Stage 2 completes, the pipeline pauses for mandatory user review.
    The user selects companies and a signal_mode, then calls promote-firmographic.
    """
    run_id_str = str(run_id)

    async with async_session() as db:
        result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            logger.error(f"Pipeline run {run_id} not found")
            return

        icp_result = await db.execute(select(ICPConfig).where(ICPConfig.id == run.icp_config_id))
        icp_config = icp_result.scalar_one_or_none()
        if not icp_config:
            logger.error(f"ICP config {run.icp_config_id} not found")
            return

        icp = icp_config.config_json
        event_collector = []

        try:
            disabled_tools = await get_disabled_tool_names(db)
        except Exception:
            disabled_tools = set()

        try:
            run.status = "running"
            run.current_stage = "industry_discovery"
            run.started_at = datetime.now(timezone.utc)
            await db.commit()

            # ════════════════════════════════════════
            # STAGE 1: Industry Discovery
            # ════════════════════════════════════════
            logger.info(f"[Stage 1] Starting industry discovery for run {run_id}")
            _emit_event(events, run_id_str, {
                "type": "stage_update",
                "stage": "industry_discovery",
                "progress": 5,
                "message": "Stage 1: Starting industry discovery...",
            })

            callback_handler = create_pipeline_callback_handler(
                events or {}, run_id_str, event_collector,
                initial_stage="industry_discovery",
                cancelled_runs=cancelled_runs,
            )
            discovery_agent = create_industry_discovery_agent(
                callback_handler=callback_handler, disabled_tools=disabled_tools,
            )
            discovery_prompt = build_industry_discovery_prompt(icp)

            discovery_result = await asyncio.to_thread(discovery_agent, discovery_prompt)
            discovery_json = parse_json_from_agent_result(discovery_result)
            discovered_raw = discovery_json.get("companies", [])
            logger.info(f"[Stage 1] Discovered {len(discovered_raw)} companies")

            if not discovered_raw:
                raise ValueError("Stage 1 discovery returned no companies")

            # Deduplicate by domain
            seen_domains = set()
            unique_companies = []
            for c in discovered_raw:
                domain = (c.get("website") or "").lower().strip()
                if domain and domain in seen_domains:
                    continue
                if domain:
                    seen_domains.add(domain)
                unique_companies.append(c)

            # Save all discovered companies to DB
            companies_saved = 0
            for disc in unique_companies:
                company = Company(
                    pipeline_run_id=run_id,
                    name=disc.get("name", "Unknown"),
                    website=disc.get("website"),
                    industry=disc.get("industry"),
                    sub_industry=disc.get("sub_industry"),
                    city=disc.get("city"),
                    state_region=disc.get("state") or disc.get("state_region"),
                    country=disc.get("country"),
                    employee_count=disc.get("employee_count"),
                    revenue_estimate=disc.get("revenue_estimate"),
                    description=disc.get("description"),
                    source=disc.get("source"),
                    current_stage="industry_discovery",
                )
                db.add(company)

                # Check cache
                if disc.get("website"):
                    cached = await find_cached_company(disc["website"], db)
                    if cached:
                        clone_company_data(cached, company)

                await db.flush()

                # Create stage result
                stage_result = CompanyStageResult(
                    company_id=company.id,
                    stage="industry_discovery",
                    status="passed",
                    reasoning=f"Discovered via {disc.get('source', 'unknown')}",
                )
                db.add(stage_result)
                companies_saved += 1

            await db.flush()

            _emit_event(events, run_id_str, {
                "type": "stage_update",
                "stage": "industry_discovery",
                "progress": 25,
                "message": f"Stage 1 complete: {companies_saved} companies discovered. Starting firmographic fit check...",
            })

            # ════════════════════════════════════════
            # STAGE 2: Firmographic Fit
            # ════════════════════════════════════════
            run.current_stage = "firmographic_fit"
            await db.commit()

            logger.info(f"[Stage 2] Starting firmographic fit for run {run_id}")
            _emit_event(events, run_id_str, {
                "type": "stage_update",
                "stage": "firmographic_fit",
                "progress": 30,
                "message": "Stage 2: Running firmographic fit check...",
            })

            # Fetch all discovered companies
            all_companies_result = await db.execute(
                select(Company).where(
                    Company.pipeline_run_id == run_id,
                    Company.current_stage == "industry_discovery",
                )
            )
            all_companies = list(all_companies_result.scalars().all())

            # Pass 1: Computational pre-filter
            passed, failed, needs_agent = quick_firmographic_filter(all_companies, icp)

            # Save failed results
            for company, reason in failed:
                company.current_stage = "firmographic_fit"
                company.qualification = "disqualified"
                company.rejection_reason = reason
                stage_result = CompanyStageResult(
                    company_id=company.id,
                    stage="firmographic_fit",
                    status="failed",
                    reasoning=reason,
                )
                db.add(stage_result)

            logger.info(
                f"[Stage 2] Pre-filter: {len(passed)} passed, {len(failed)} failed, "
                f"{len(needs_agent)} need agent verification"
            )

            # Pass 2: Agent verification in batches of 8
            companies_to_verify = passed + needs_agent
            companies_passed = 0
            companies_failed_agent = 0

            for batch_idx, batch in enumerate(_chunk(companies_to_verify, 8)):
                batch_dicts = []
                batch_map = {}
                for c in batch:
                    cdict = {
                        "name": c.name,
                        "website": c.website,
                        "industry": c.industry,
                        "sub_industry": c.sub_industry,
                        "country": c.country,
                        "employee_count": c.employee_count,
                        "revenue_estimate": c.revenue_estimate,
                        "description": (c.description or "")[:200],
                    }
                    if c.cached_from_run_id:
                        cdict["existing_data"] = True
                        cdict["data_freshness"] = str(c.data_freshness) if c.data_freshness else None
                    batch_dicts.append(cdict)
                    batch_map[(c.website or "").lower()] = c

                _emit_event(events, run_id_str, {
                    "type": "stage_update",
                    "stage": "firmographic_fit",
                    "progress": 35 + int(25 * (batch_idx + 1) / max(len(list(_chunk(companies_to_verify, 8))), 1)),
                    "message": f"Stage 2: Evaluating batch {batch_idx + 1} ({len(batch)} companies)...",
                })

                try:
                    fit_callback = create_pipeline_callback_handler(
                        events or {}, run_id_str, event_collector,
                        initial_stage="firmographic_fit",
                        cancelled_runs=cancelled_runs,
                    )
                    fit_agent = create_firmographic_fit_agent(
                        callback_handler=fit_callback, disabled_tools=disabled_tools,
                    )
                    fit_prompt = build_firmographic_fit_prompt(batch_dicts, icp)
                    fit_result = await asyncio.to_thread(fit_agent, fit_prompt)
                    fit_json = parse_json_from_agent_result(fit_result)

                    for evaluated in fit_json.get("companies", []):
                        domain = (evaluated.get("website") or "").lower()
                        company = batch_map.get(domain)
                        if not company:
                            # Try name match as fallback
                            for c in batch:
                                if c.name and c.name.lower() == (evaluated.get("name") or "").lower():
                                    company = c
                                    break
                        if not company:
                            continue

                        recommendation = evaluated.get("recommendation", "pass")
                        score = _normalize_score_to_100(evaluated.get("score", 50))
                        reasoning = evaluated.get("reasoning", "")

                        company.current_stage = "firmographic_fit"
                        company.icp_match_score = score

                        # Update employee/revenue if agent found better data
                        if evaluated.get("employee_count"):
                            company.employee_count = evaluated["employee_count"]
                        if evaluated.get("revenue_estimate"):
                            company.revenue_estimate = evaluated["revenue_estimate"]

                        if recommendation == "pass":
                            company.qualification = "qualified"
                            stage_result = CompanyStageResult(
                                company_id=company.id,
                                stage="firmographic_fit",
                                status="passed",
                                score=score,
                                reasoning=reasoning,
                                evidence=evaluated.get("per_criterion"),
                            )
                            companies_passed += 1
                        else:
                            company.qualification = "disqualified"
                            company.rejection_reason = reasoning
                            stage_result = CompanyStageResult(
                                company_id=company.id,
                                stage="firmographic_fit",
                                status="failed",
                                score=score,
                                reasoning=reasoning,
                                evidence=evaluated.get("per_criterion"),
                            )
                            companies_failed_agent += 1

                        db.add(stage_result)

                except PipelineCancelled:
                    raise
                except Exception as batch_err:
                    logger.warning(f"[Stage 2] Batch {batch_idx + 1} agent failed: {batch_err}. Marking as needs review.")
                    for c in batch:
                        if c.current_stage != "firmographic_fit":
                            c.current_stage = "firmographic_fit"
                            c.qualification = "qualified"
                            c.icp_match_score = 50  # Default middle score
                            stage_result = CompanyStageResult(
                                company_id=c.id,
                                stage="firmographic_fit",
                                status="passed",
                                score=50,
                                reasoning="Agent verification failed; defaulted to pass for user review",
                            )
                            db.add(stage_result)
                            companies_passed += 1

            await db.flush()

            # Update company counts
            run.companies_found = companies_saved

            # ════════════════════════════════════════
            # PAUSE: Mandatory user review
            # ════════════════════════════════════════
            await _persist_logs(db, run_id, event_collector)

            run.status = "awaiting_review"
            run.current_stage = "review_firmographic"
            run.stage_details = {
                "total_discovered": companies_saved,
                "pre_filter_passed": len(passed),
                "pre_filter_failed": len(failed),
                "agent_passed": companies_passed,
                "agent_failed": companies_failed_agent,
            }
            await db.commit()

            # Generate embeddings
            try:
                from app.services.embedding_service import embed_company
                company_results = await db.execute(
                    select(Company).where(Company.pipeline_run_id == run_id)
                )
                for comp in company_results.scalars().all():
                    if comp.embedding is None:
                        await embed_company(comp, db)
                await db.commit()
            except Exception as embed_err:
                logger.warning(f"Embedding generation failed (non-fatal): {embed_err}")

            total_failed = len(failed) + companies_failed_agent
            _emit_event(events, run_id_str, {
                "type": "awaiting_firmographic_review",
                "companies_passed": companies_passed,
                "companies_failed": total_failed,
                "total": companies_saved,
            })

            logger.info(
                f"Pipeline {run_id} paused for firmographic review: "
                f"{companies_passed} passed, {total_failed} failed out of {companies_saved}"
            )

        except PipelineCancelled:
            logger.info(f"Pipeline {run_id} cancelled by user")
            if cancelled_runs is not None:
                cancelled_runs.discard(run_id_str)
            await _handle_pipeline_error(db, run_id, run, event_collector, events, run_id_str, None, cancelled=True)

        except Exception as e:
            logger.error(f"Pipeline {run_id} failed: {e}\n{traceback.format_exc()}")
            await _handle_pipeline_error(db, run_id, run, event_collector, events, run_id_str, e)


# ──────────────────────────────────────────────────────────────────
# Resume after firmographic review → Stage 3 signals
# ──────────────────────────────────────────────────────────────────

async def resume_after_firmographic(
    run_id: UUID,
    company_ids: list[UUID],
    signal_mode: str,
    events: dict = None,
    cancelled_runs: set = None,
):
    """Resume pipeline after firmographic review. Runs signal research (Stage 3).

    signal_mode: "budget_first" | "urgency_first" | "both"
    """
    run_id_str = str(run_id)

    async with async_session() as db:
        result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            return

        icp_result = await db.execute(select(ICPConfig).where(ICPConfig.id == run.icp_config_id))
        icp_config = icp_result.scalar_one_or_none()
        if not icp_config:
            return

        icp = icp_config.config_json
        event_collector = []

        try:
            disabled_tools = await get_disabled_tool_names(db)
        except Exception:
            disabled_tools = set()

        try:
            # Mark selected companies as promoted, others as excluded
            all_companies_result = await db.execute(
                select(Company).where(
                    Company.pipeline_run_id == run_id,
                    Company.current_stage == "firmographic_fit",
                    Company.qualification != "disqualified",
                )
            )
            for company in all_companies_result.scalars().all():
                if company.id in company_ids:
                    company.promoted = True
                    stage_result = CompanyStageResult(
                        company_id=company.id,
                        stage="firmographic_fit",
                        status="promoted",
                        user_override=True,
                    )
                    db.add(stage_result)
                else:
                    company.promoted = False
                    stage_result = CompanyStageResult(
                        company_id=company.id,
                        stage="firmographic_fit",
                        status="excluded",
                        user_override=False,
                        reasoning="User deselected at firmographic review",
                    )
                    db.add(stage_result)

            run.signal_mode = signal_mode
            run.status = "running"
            await db.commit()

            # Fetch promoted companies
            promoted_result = await db.execute(
                select(Company).where(
                    Company.pipeline_run_id == run_id,
                    Company.promoted == True,
                )
            )
            promoted_companies = list(promoted_result.scalars().all())

            if not promoted_companies:
                run.status = "completed"
                run.current_stage = "completed"
                run.completed_at = datetime.now(timezone.utc)
                await db.commit()
                _emit_event(events, run_id_str, {"type": "completed", "companies_found": 0, "contacts_found": 0})
                return

            log_offset = await _get_existing_log_count(db, run_id)

            if signal_mode == "both":
                # Run BOTH budget + urgency signals in one pass
                run.current_stage = "budget_urgency_signals"
                await db.commit()

                await _run_signal_research(
                    db, run, promoted_companies, icp, "both",
                    events, run_id_str, event_collector, cancelled_runs, disabled_tools,
                )

                await _persist_logs(db, run_id, event_collector, offset=log_offset)
                run.status = "awaiting_review"
                run.current_stage = "review_signals"
                await db.commit()

                avg_budget = sum(c.budget_signal_score or 0 for c in promoted_companies) / max(len(promoted_companies), 1)
                avg_urgency = sum(c.urgency_signal_score or 0 for c in promoted_companies) / max(len(promoted_companies), 1)

                _emit_event(events, run_id_str, {
                    "type": "awaiting_signal_review",
                    "companies_scored": len(promoted_companies),
                    "avg_budget": round(avg_budget, 1),
                    "avg_urgency": round(avg_urgency, 1),
                })

            else:
                # Serial mode: run first signal type only
                first_type = "budget_signals" if signal_mode == "budget_first" else "urgency_signals"
                run.current_stage = first_type
                await db.commit()

                await _run_signal_research(
                    db, run, promoted_companies, icp, first_type,
                    events, run_id_str, event_collector, cancelled_runs, disabled_tools,
                )

                await _persist_logs(db, run_id, event_collector, offset=log_offset)
                run.signal_phase = "first_signal_done"
                run.status = "awaiting_review"
                run.current_stage = f"review_{first_type}"
                await db.commit()

                score_attr = "budget_signal_score" if first_type == "budget_signals" else "urgency_signal_score"
                avg_score = sum(getattr(c, score_attr) or 0 for c in promoted_companies) / max(len(promoted_companies), 1)

                _emit_event(events, run_id_str, {
                    "type": "awaiting_first_signal_review",
                    "signal_type": first_type,
                    "companies_scored": len(promoted_companies),
                    "avg_score": round(avg_score, 1),
                })

        except PipelineCancelled:
            if cancelled_runs is not None:
                cancelled_runs.discard(run_id_str)
            await _handle_pipeline_error(db, run_id, run, event_collector, events, run_id_str, None, cancelled=True)
        except Exception as e:
            logger.error(f"Pipeline resume {run_id} failed: {e}\n{traceback.format_exc()}")
            await _handle_pipeline_error(db, run_id, run, event_collector, events, run_id_str, e)


# ──────────────────────────────────────────────────────────────────
# Resume after first signal review (serial mode only)
# ──────────────────────────────────────────────────────────────────

async def resume_after_first_signal(
    run_id: UUID,
    company_ids: list[UUID],
    events: dict = None,
    cancelled_runs: set = None,
):
    """Resume after reviewing first signal results in serial mode.
    Runs the second signal type."""
    run_id_str = str(run_id)

    async with async_session() as db:
        result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            return

        icp_result = await db.execute(select(ICPConfig).where(ICPConfig.id == run.icp_config_id))
        icp_config = icp_result.scalar_one_or_none()
        if not icp_config:
            return

        icp = icp_config.config_json
        event_collector = []

        try:
            disabled_tools = await get_disabled_tool_names(db)
        except Exception:
            disabled_tools = set()

        try:
            # Mark selections
            promoted_result = await db.execute(
                select(Company).where(
                    Company.pipeline_run_id == run_id,
                    Company.promoted == True,
                )
            )
            for company in promoted_result.scalars().all():
                if company.id not in company_ids:
                    company.promoted = False
                    first_type = "budget_signals" if run.signal_mode == "budget_first" else "urgency_signals"
                    stage_result = CompanyStageResult(
                        company_id=company.id,
                        stage=first_type,
                        status="excluded",
                        user_override=False,
                        reasoning=f"User deselected after {first_type.replace('_', ' ')} review",
                    )
                    db.add(stage_result)

            # Determine second signal type
            second_type = "urgency_signals" if run.signal_mode == "budget_first" else "budget_signals"

            run.status = "running"
            run.current_stage = second_type
            await db.commit()

            # Fetch still-promoted companies
            promoted_result = await db.execute(
                select(Company).where(
                    Company.pipeline_run_id == run_id,
                    Company.promoted == True,
                )
            )
            promoted_companies = list(promoted_result.scalars().all())

            if not promoted_companies:
                run.status = "completed"
                run.current_stage = "completed"
                run.completed_at = datetime.now(timezone.utc)
                await db.commit()
                _emit_event(events, run_id_str, {"type": "completed", "companies_found": 0, "contacts_found": 0})
                return

            log_offset = await _get_existing_log_count(db, run_id)

            await _run_signal_research(
                db, run, promoted_companies, icp, second_type,
                events, run_id_str, event_collector, cancelled_runs, disabled_tools,
            )

            await _persist_logs(db, run_id, event_collector, offset=log_offset)
            run.signal_phase = "second_signal_done"
            run.status = "awaiting_review"
            run.current_stage = f"review_{second_type}"
            await db.commit()

            score_attr = "budget_signal_score" if second_type == "budget_signals" else "urgency_signal_score"
            avg_score = sum(getattr(c, score_attr) or 0 for c in promoted_companies) / max(len(promoted_companies), 1)

            _emit_event(events, run_id_str, {
                "type": "awaiting_second_signal_review",
                "signal_type": second_type,
                "companies_scored": len(promoted_companies),
                "avg_score": round(avg_score, 1),
            })

        except PipelineCancelled:
            if cancelled_runs is not None:
                cancelled_runs.discard(run_id_str)
            await _handle_pipeline_error(db, run_id, run, event_collector, events, run_id_str, None, cancelled=True)
        except Exception as e:
            logger.error(f"Pipeline resume {run_id} failed: {e}\n{traceback.format_exc()}")
            await _handle_pipeline_error(db, run_id, run, event_collector, events, run_id_str, e)


# ──────────────────────────────────────────────────────────────────
# Resume after final signal review → Stages 4 + 5
# ──────────────────────────────────────────────────────────────────

async def resume_after_signals(
    run_id: UUID,
    company_ids: list[UUID],
    events: dict = None,
    cancelled_runs: set = None,
):
    """Resume after final signal review. Runs Stages 4 (contacts) + 5 (scoring)."""
    run_id_str = str(run_id)

    async with async_session() as db:
        result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            return

        icp_result = await db.execute(select(ICPConfig).where(ICPConfig.id == run.icp_config_id))
        icp_config = icp_result.scalar_one_or_none()
        if not icp_config:
            return

        icp = icp_config.config_json
        event_collector = []

        try:
            disabled_tools = await get_disabled_tool_names(db)
        except Exception:
            disabled_tools = set()

        try:
            # Mark final selections
            promoted_result = await db.execute(
                select(Company).where(
                    Company.pipeline_run_id == run_id,
                    Company.promoted == True,
                )
            )
            for company in promoted_result.scalars().all():
                if company.id not in company_ids:
                    company.promoted = False

            run.status = "running"
            run.current_stage = "contact_discovery"
            await db.commit()

            # Fetch final promoted companies
            promoted_result = await db.execute(
                select(Company).where(
                    Company.pipeline_run_id == run_id,
                    Company.promoted == True,
                )
            )
            promoted_companies = list(promoted_result.scalars().all())

            if not promoted_companies:
                run.status = "completed"
                run.current_stage = "completed"
                run.completed_at = datetime.now(timezone.utc)
                await db.commit()
                _emit_event(events, run_id_str, {"type": "completed", "companies_found": 0, "contacts_found": 0})
                return

            total_companies = len(promoted_companies)
            log_offset = await _get_existing_log_count(db, run_id)

            # ════════════════════════════════════════
            # STAGE 4: Contact Discovery
            # ════════════════════════════════════════
            _emit_event(events, run_id_str, {
                "type": "stage_update",
                "stage": "contact_discovery",
                "progress": 60,
                "message": f"Stage 4: Finding contacts for {total_companies} companies...",
            })

            contacts_total = 0
            for i, company in enumerate(promoted_companies):
                # Update stage_details for polling-based progress
                run.stage_details = {
                    **(run.stage_details or {}),
                    "current_company_index": i + 1,
                    "total_companies_in_stage": total_companies,
                    "current_company_name": company.name,
                    "contacts_found_so_far": contacts_total,
                }
                await db.commit()

                _emit_event(events, run_id_str, {
                    "type": "company_start",
                    "company_name": company.name,
                    "company_index": i + 1,
                    "total_companies": total_companies,
                    "stage": "contact_discovery",
                    "progress": 60 + int(25 * (i + 1) / total_companies),
                })

                try:
                    # Get cached contacts if any
                    cached_contacts = None
                    if company.cached_from_run_id:
                        cached_result = await db.execute(
                            select(Contact).where(Contact.company_id == company.id)
                        )
                        existing = cached_result.scalars().all()
                        if existing:
                            cached_contacts = [
                                {
                                    "full_name": c.full_name,
                                    "designation": c.designation,
                                    "email": c.email,
                                    "linkedin_url": c.linkedin_url,
                                    "source": c.source,
                                }
                                for c in existing
                            ]

                    contact_callback = create_pipeline_callback_handler(
                        events or {}, run_id_str, event_collector,
                        initial_stage="contact_discovery",
                        cancelled_runs=cancelled_runs,
                    )
                    contact_agent = create_contact_agent(
                        callback_handler=contact_callback, disabled_tools=disabled_tools,
                    )

                    company_dict = {
                        "name": company.name,
                        "website": company.website,
                        "industry": company.industry,
                        "employee_count": company.employee_count,
                    }
                    contact_prompt = build_contact_discovery_prompt(company_dict, icp, cached_contacts)

                    contact_result = await asyncio.to_thread(contact_agent, contact_prompt)
                    contact_json = parse_json_from_agent_result(contact_result)

                    contacts_saved = 0
                    for cd in contact_json.get("contacts", []):
                        contact = Contact(
                            company_id=company.id,
                            full_name=cd.get("full_name"),
                            first_name=cd.get("first_name"),
                            last_name=cd.get("last_name"),
                            designation=cd.get("designation"),
                            role_category=cd.get("role_category"),
                            email=cd.get("email"),
                            phone=cd.get("phone"),
                            linkedin_url=cd.get("linkedin_url"),
                            source=cd.get("source"),
                            confidence=cd.get("confidence"),
                            enrichment_status=cd.get("enrichment_status", "pending"),
                        )
                        db.add(contact)
                        contacts_saved += 1

                    company.current_stage = "contact_discovery"
                    stage_result = CompanyStageResult(
                        company_id=company.id,
                        stage="contact_discovery",
                        status="passed" if contacts_saved > 0 else "skipped",
                        score=float(contacts_saved),
                        reasoning=f"Found {contacts_saved} contacts",
                    )
                    db.add(stage_result)
                    contacts_total += contacts_saved

                    _emit_event(events, run_id_str, {
                        "type": "company_stage_result",
                        "company_name": company.name,
                        "stage": "contact_discovery",
                        "status": "passed" if contacts_saved > 0 else "skipped",
                        "score": contacts_saved,
                    })

                except PipelineCancelled:
                    raise
                except Exception as err:
                    logger.warning(f"[Stage 4] Contact discovery failed for {company.name}: {err}")
                    company.current_stage = "contact_discovery"

                await db.flush()

            # ════════════════════════════════════════
            # STAGE 5: Final Scoring & Ranking
            # ════════════════════════════════════════
            run.current_stage = "final_scoring"
            await db.commit()

            _emit_event(events, run_id_str, {
                "type": "stage_update",
                "stage": "final_scoring",
                "progress": 90,
                "message": "Stage 5: Computing final scores and ranking...",
            })

            # Re-fetch with contacts loaded
            from sqlalchemy.orm import selectinload
            promoted_result = await db.execute(
                select(Company)
                .where(Company.pipeline_run_id == run_id, Company.promoted == True)
                .options(selectinload(Company.contacts))
            )
            promoted_companies = list(promoted_result.scalars().unique().all())

            for company in promoted_companies:
                company.final_score = compute_final_score(company)
                company.current_stage = "final_scoring"
                company.data_freshness = datetime.now(timezone.utc)

            # Rank by final score
            ranked = sorted(promoted_companies, key=lambda c: c.final_score or 0, reverse=True)
            for i, c in enumerate(ranked):
                c.final_rank = i + 1

            # Persist logs
            await _persist_logs(db, run_id, event_collector, offset=log_offset)

            run.status = "completed"
            run.current_stage = "completed"
            run.contacts_found = contacts_total
            run.completed_at = datetime.now(timezone.utc)
            await db.commit()

            # Generate embeddings
            try:
                from app.services.embedding_service import embed_company
                for comp in promoted_companies:
                    if comp.embedding is None:
                        await embed_company(comp, db)
                await db.commit()
            except Exception as embed_err:
                logger.warning(f"Embedding generation failed (non-fatal): {embed_err}")

            avg_final = sum(c.final_score or 0 for c in promoted_companies) / max(len(promoted_companies), 1)

            _emit_event(events, run_id_str, {
                "type": "completed",
                "companies_found": len(promoted_companies),
                "contacts_found": contacts_total,
                "avg_final_score": round(avg_final, 1),
            })

            logger.info(
                f"Pipeline {run_id} completed: {len(promoted_companies)} companies, "
                f"{contacts_total} contacts, avg score {avg_final:.1f}"
            )

        except PipelineCancelled:
            if cancelled_runs is not None:
                cancelled_runs.discard(run_id_str)
            await _handle_pipeline_error(db, run_id, run, event_collector, events, run_id_str, None, cancelled=True)
        except Exception as e:
            logger.error(f"Pipeline resume {run_id} failed: {e}\n{traceback.format_exc()}")
            await _handle_pipeline_error(db, run_id, run, event_collector, events, run_id_str, e)


# ──────────────────────────────────────────────────────────────────
# Signal research helper (used by resume_after_firmographic and resume_after_first_signal)
# ──────────────────────────────────────────────────────────────────

async def _run_signal_research(
    db, run, companies, icp, signal_type,
    events, run_id_str, event_collector, cancelled_runs, disabled_tools,
):
    """Run signal research for a list of companies.

    signal_type: "budget_signals", "urgency_signals", or "both"
    """
    stage_name = {
        "budget_signals": "Budget Signal Research",
        "urgency_signals": "Urgency Signal Research",
        "both": "Budget & Urgency Signal Research",
    }.get(signal_type, signal_type)

    _emit_event(events, run_id_str, {
        "type": "stage_update",
        "stage": signal_type if signal_type != "both" else "budget_urgency_signals",
        "progress": 40,
        "message": f"Stage 3: {stage_name} for {len(companies)} companies...",
    })

    for i, company in enumerate(companies):
        # Update stage_details for polling-based progress
        run.stage_details = {
            **(run.stage_details or {}),
            "current_company_index": i + 1,
            "total_companies_in_stage": len(companies),
            "current_company_name": company.name,
        }
        await db.commit()

        _emit_event(events, run_id_str, {
            "type": "company_start",
            "company_name": company.name,
            "company_index": i + 1,
            "total_companies": len(companies),
            "stage": signal_type if signal_type != "both" else "budget_urgency_signals",
            "progress": 40 + int(20 * (i + 1) / len(companies)),
        })

        try:
            signal_callback = create_pipeline_callback_handler(
                events or {}, run_id_str, event_collector,
                initial_stage=signal_type if signal_type != "both" else "budget_urgency_signals",
                cancelled_runs=cancelled_runs,
            )
            agent = create_signal_agent(
                callback_handler=signal_callback, disabled_tools=disabled_tools,
            )

            company_dict = {
                "name": company.name,
                "website": company.website,
                "description": company.description,
                "employee_count": company.employee_count,
                "revenue_estimate": company.revenue_estimate,
                "cached_from_run_id": str(company.cached_from_run_id) if company.cached_from_run_id else None,
                "data_freshness": str(company.data_freshness) if company.data_freshness else None,
            }

            prompt = build_signal_prompt(company_dict, icp, signal_type)
            result = await asyncio.to_thread(agent, prompt)
            signal_json = parse_json_from_agent_result(result)

            # Update scores (normalize to 0-100 scale)
            if signal_type in ("budget_signals", "both"):
                budget_score = signal_json.get("budget_signal_score") or signal_json.get("composite_score", 0)
                company.budget_signal_score = _normalize_score_to_100(float(budget_score) if budget_score else None)

            if signal_type in ("urgency_signals", "both"):
                urgency_score = signal_json.get("urgency_signal_score") or signal_json.get("composite_score", 0)
                company.urgency_signal_score = _normalize_score_to_100(float(urgency_score) if urgency_score else None)

            # Create stage results
            signals_data = signal_json.get("signals", [])

            if signal_type in ("budget_signals", "both"):
                budget_signals = [s for s in signals_data if s.get("type") == "budget"] if signal_type == "both" else signals_data
                stage_result = CompanyStageResult(
                    company_id=company.id,
                    stage="budget_signals",
                    status="passed",
                    score=company.budget_signal_score,
                    reasoning=f"Budget signal score: {company.budget_signal_score}/100",
                    evidence=budget_signals[:10] if budget_signals else None,
                )
                db.add(stage_result)

            if signal_type in ("urgency_signals", "both"):
                urgency_signals = [s for s in signals_data if s.get("type") == "urgency"] if signal_type == "both" else signals_data
                stage_result = CompanyStageResult(
                    company_id=company.id,
                    stage="urgency_signals",
                    status="passed",
                    score=company.urgency_signal_score,
                    reasoning=f"Urgency signal score: {company.urgency_signal_score}/100",
                    evidence=urgency_signals[:10] if urgency_signals else None,
                )
                db.add(stage_result)

            # Update current_stage to reflect signal completion
            if signal_type == "both":
                company.current_stage = "budget_urgency_signals"
            else:
                company.current_stage = signal_type

            _emit_event(events, run_id_str, {
                "type": "company_stage_result",
                "company_name": company.name,
                "stage": signal_type,
                "status": "passed",
                "score": _normalize_score_to_100(signal_json.get("composite_score", 0)),
            })

        except PipelineCancelled:
            raise
        except Exception as err:
            logger.warning(f"[Stage 3] Signal research failed for {company.name}: {err}")
            # Still update current_stage so the company is visible at this stage
            if signal_type == "both":
                company.current_stage = "budget_urgency_signals"
            else:
                company.current_stage = signal_type

        await db.flush()
