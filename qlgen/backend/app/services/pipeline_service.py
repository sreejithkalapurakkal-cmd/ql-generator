import asyncio
import json
import logging
import traceback
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import select

from app.agent.lead_gen_agent import (
    create_discovery_agent,
    create_contact_agent,
    create_bant_agent,
    create_pipeline_callback_handler,
    PipelineCancelled,
)
from app.agent.prompt_builder import build_discovery_prompt, build_contact_prompt, build_bant_prompt
from app.db.session import async_session
from app.models.pipeline import PipelineRun
from app.models.icp import ICPConfig
from app.models.company import Company
from app.models.contact import Contact
from app.models.bant import BANTScore
from app.models.pipeline_log import PipelineLog

logger = logging.getLogger(__name__)


def _compute_weighted_bant_score(bant_data: dict, options: dict) -> int:
    budget = bant_data.get("budget_score") or 0
    authority = bant_data.get("authority_score") or 0
    need = bant_data.get("need_score") or 0
    timing = bant_data.get("timing_score") or 0

    weights = options.get("bant_weights", {})
    w_b = weights.get("budget", 3)
    w_a = weights.get("authority", 3)
    w_n = weights.get("need", 3)
    w_t = weights.get("timing", 3)

    weights_sum = w_b + w_a + w_n + w_t
    if weights_sum == 0:
        return budget + authority + need + timing

    weighted_avg = (budget * w_b + authority * w_a + need * w_n + timing * w_t) / weights_sum
    return round(weighted_avg * 4)


def _emit_event(events: dict, run_id: str, event: dict):
    """Add event to the SSE event list."""
    if events is not None and run_id in events:
        events[run_id].append(event)


def _repair_truncated_json(text: str) -> str:
    """Attempt to repair truncated JSON by closing open strings, arrays, and objects."""
    # Track parser state
    in_string = False
    escape_next = False
    stack = []  # stack of open brackets: '{' or '['

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
    # If we ended inside a string, close it
    if in_string:
        repaired += '"'

    # Close any remaining open brackets in reverse order
    for bracket in reversed(stack):
        repaired += '}' if bracket == '{' else ']'

    return repaired


def _truncate_to_last_complete_item(text: str) -> str:
    """Cut JSON text back to the last cleanly-closed array element or object value.

    This finds the last '},' or '}]' pattern that plausibly ends a complete
    companies/contacts entry, trims there, and lets _repair_truncated_json
    close the remaining brackets.
    """
    # Find the last position where a complete object ended before more data
    # Pattern: '},\n' or '}, ' — indicates a complete array element
    last_obj_end = -1
    for marker in ['},\n', '},\r', '}, ']:
        pos = text.rfind(marker)
        if pos > last_obj_end:
            last_obj_end = pos

    if last_obj_end > 0:
        return text[: last_obj_end + 1]  # include the closing '}'

    return text


def parse_json_from_agent_result(result) -> dict:
    """Extract JSON from the agent's text response, repairing truncation if needed."""
    text = str(result)

    # Try to find JSON block in markdown code fence
    if "```json" in text:
        start = text.index("```json") + 7
        closing = text.find("```", start)
        if closing != -1:
            text = text[start:closing].strip()
        else:
            text = text[start:].strip()
    elif "```" in text:
        start = text.index("```") + 3
        closing = text.find("```", start)
        if closing != -1:
            text = text[start:closing].strip()
        else:
            text = text[start:].strip()

    # Try to find the largest JSON object by matching braces
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

    # 1) Try parsing as-is first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2) Try repairing truncated JSON directly (close open strings/brackets)
    try:
        repaired = _repair_truncated_json(text)
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # 3) Truncate back to the last complete array element, then repair
    try:
        truncated = _truncate_to_last_complete_item(text)
        repaired = _repair_truncated_json(truncated)
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # 4) Last resort: raise with the original text for debugging
    logger.error(f"Failed to parse agent JSON (length={len(text)}). First 500 chars: {text[:500]}")
    return json.loads(text)  # will raise the original JSONDecodeError


async def execute_pipeline(run_id: UUID, events: dict = None, cancelled_runs: set = None):
    """Multi-phase pipeline execution with per-company specialized agents.

    Phase 1 — Discovery: Agent uses discover_icp_companies tool to find 50+ candidates,
    scores them against ICP, classifies into tiers.

    Phase 2 — Contact Discovery: For each company individually, a Contact Agent finds
    decision-maker contacts and gathers research data (financials, news, tech signals).

    Phase 3 — BANT Scoring: For each company individually, a BANT Agent produces
    evidence-based scores using the pre-gathered research data.

    Results are saved to DB incrementally per company for error isolation.
    """
    run_id_str = str(run_id)

    async with async_session() as db:
        # Fetch pipeline run
        result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            logger.error(f"Pipeline run {run_id} not found")
            return

        # Fetch ICP config
        icp_result = await db.execute(
            select(ICPConfig).where(ICPConfig.id == run.icp_config_id)
        )
        icp_config = icp_result.scalar_one_or_none()
        if not icp_config:
            logger.error(f"ICP config {run.icp_config_id} not found")
            return

        icp = icp_config.config_json
        options = run.options or {}
        event_collector = []

        try:
            # Mark pipeline as running
            run.status = "running"
            run.current_stage = "company_discovery"
            run.started_at = datetime.now(timezone.utc)
            await db.commit()

            _emit_event(events, run_id_str, {
                "type": "stage_update",
                "stage": "company_discovery",
                "progress": 5,
                "message": "Phase 1: Starting company discovery...",
            })

            # ════════════════════════════════════════
            # PHASE 1: Company Discovery
            # ════════════════════════════════════════
            logger.info(f"[Phase 1] Creating discovery agent for run {run_id}")
            callback_handler = create_pipeline_callback_handler(
                events or {}, run_id_str, event_collector,
                cancelled_runs=cancelled_runs,
            )
            discovery_agent = create_discovery_agent(callback_handler=callback_handler)
            discovery_prompt = build_discovery_prompt(icp, options)

            logger.info(f"[Phase 1] Invoking discovery agent for run {run_id}")
            discovery_result = await asyncio.to_thread(discovery_agent, discovery_prompt)
            discovery_text = str(discovery_result)
            logger.info(
                f"[Phase 1] Discovery complete. Result length: {len(discovery_text)}, "
                f"first 500 chars: {discovery_text[:500]}"
            )

            _emit_event(events, run_id_str, {
                "type": "stage_update",
                "stage": "company_discovery",
                "progress": 30,
                "message": "Phase 1 complete. Parsing discovered companies...",
            })

            # Parse Phase 1 results
            discovery_json = parse_json_from_agent_result(discovery_result)
            discovered_companies = discovery_json.get("companies", [])
            logger.info(f"[Phase 1] Parsed {len(discovered_companies)} companies from discovery")

            # Log discovery summary if present
            discovery_summary = discovery_json.get("discovery_summary")
            if discovery_summary:
                logger.info(f"[Phase 1] Discovery summary: {json.dumps(discovery_summary, default=str)}")
                _emit_event(events, run_id_str, {
                    "type": "agent_reasoning",
                    "text": (
                        f"Discovery complete: {discovery_summary.get('verified_match_count', 0)} verified, "
                        f"{discovery_summary.get('potential_match_count', 0)} potential, "
                        f"{discovery_summary.get('weak_match_count', 0)} weak matches "
                        f"from {discovery_summary.get('total_candidates_found', '?')} candidates."
                    ),
                    "stage": "company_discovery",
                })

            if not discovered_companies:
                raise ValueError("Phase 1 discovery returned no companies")

            # Deduplicate by website/domain
            seen_domains = set()
            unique_companies = []
            for c in discovered_companies:
                domain = (c.get("website") or "").lower().strip()
                if domain and domain in seen_domains:
                    continue
                if domain:
                    seen_domains.add(domain)
                unique_companies.append(c)
            discovered_companies = unique_companies
            logger.info(f"[Phase 1] {len(discovered_companies)} unique companies after dedup")

            # ════════════════════════════════════════
            # MULTI-STEP MODE: Pause after Phase 1
            # ════════════════════════════════════════
            pipeline_mode = options.get("pipeline_mode", "single_run")
            if pipeline_mode == "multi_step":
                logger.info(f"[Multi-step] Saving {len(discovered_companies)} discovered companies and pausing for review")

                companies_saved = 0
                for disc_company in discovered_companies:
                    company_data = dict(disc_company)
                    company_data.setdefault("source", "discover_icp_companies")
                    company = Company(
                        pipeline_run_id=run_id,
                        name=company_data.get("name", "Unknown"),
                        website=company_data.get("website"),
                        industry=company_data.get("industry"),
                        sub_industry=company_data.get("sub_industry"),
                        city=company_data.get("city"),
                        state_region=company_data.get("state"),
                        country=company_data.get("country"),
                        employee_count=company_data.get("employee_count"),
                        revenue_estimate=company_data.get("revenue_estimate"),
                        tech_stack_json=company_data.get("tech_signals"),
                        description=company_data.get("description"),
                        source=company_data.get("source"),
                        icp_match_score=company_data.get("icp_match_score"),
                        match_reasoning=company_data.get("match_reasoning"),
                        qualification=company_data.get("qualification", "good_fit"),
                        raw_data_json=company_data.get("dimension_evidence"),
                    )
                    db.add(company)
                    companies_saved += 1

                await db.flush()

                # Persist Phase 1 agent logs
                for seq, event_data in enumerate(event_collector):
                    log = PipelineLog(
                        pipeline_run_id=run_id,
                        event_type=event_data.get("type", "unknown"),
                        event_data=event_data,
                        sequence_number=seq,
                    )
                    db.add(log)

                # Update run status
                run.status = "awaiting_review"
                run.current_stage = "review"
                run.companies_found = companies_saved
                run.stage_details = {
                    "total_discovered": companies_saved,
                    "discovery_completed_at": datetime.now(timezone.utc).isoformat(),
                }
                await db.commit()

                # Generate embeddings for discovered companies
                try:
                    from app.services.embedding_service import embed_company
                    company_results = await db.execute(
                        select(Company).where(Company.pipeline_run_id == run_id)
                    )
                    for comp in company_results.scalars().all():
                        await embed_company(comp, db)
                    await db.commit()
                    logger.info(f"Embeddings generated for {companies_saved} discovered companies in run {run_id}")
                except Exception as embed_err:
                    logger.warning(f"Embedding generation failed (non-fatal): {embed_err}")

                _emit_event(events, run_id_str, {
                    "type": "awaiting_review",
                    "companies_found": companies_saved,
                })

                logger.info(
                    f"Pipeline {run_id} paused for review: {companies_saved} companies discovered"
                )
                return  # Pipeline pauses here

            # ════════════════════════════════════════
            # SINGLE-RUN MODE: Phase 2 & 3
            # ════════════════════════════════════════
            total_companies = len(discovered_companies)
            _emit_event(events, run_id_str, {
                "type": "stage_update",
                "stage": "contact_discovery",
                "progress": 35,
                "message": f"Phase 2-3: Researching {total_companies} companies individually...",
            })

            run.current_stage = "contact_discovery"
            await db.commit()

            companies_saved = 0
            contacts_saved = 0

            for i, disc_company in enumerate(discovered_companies):
                company_data = dict(disc_company)
                company_data.setdefault("source", "discover_icp_companies")

                company, new_contacts = await _process_company_phases_2_3(
                    db=db,
                    run_id=run_id,
                    disc_company=disc_company,
                    company_data=company_data,
                    icp=icp,
                    events=events,
                    run_id_str=run_id_str,
                    event_collector=event_collector,
                    company_index=i,
                    total_companies=total_companies,
                    cancelled_runs=cancelled_runs,
                    options=options,
                )
                companies_saved += 1
                contacts_saved += new_contacts

            # Persist agent logs
            for seq, event_data in enumerate(event_collector):
                log = PipelineLog(
                    pipeline_run_id=run_id,
                    event_type=event_data.get("type", "unknown"),
                    event_data=event_data,
                    sequence_number=seq,
                )
                db.add(log)

            # Mark completed
            run.status = "completed"
            run.current_stage = "completed"
            run.companies_found = companies_saved
            run.contacts_found = contacts_saved
            run.completed_at = datetime.now(timezone.utc)
            await db.commit()

            # Generate embeddings for newly saved companies
            try:
                from app.services.embedding_service import embed_company
                company_results = await db.execute(
                    select(Company).where(Company.pipeline_run_id == run_id)
                )
                for comp in company_results.scalars().all():
                    await embed_company(comp, db)
                await db.commit()
                logger.info(f"Embeddings generated for {companies_saved} companies in run {run_id}")
            except Exception as embed_err:
                logger.warning(f"Embedding generation failed (non-fatal): {embed_err}")

            _emit_event(events, run_id_str, {
                "type": "completed",
                "companies_found": companies_saved,
                "contacts_found": contacts_saved,
            })

            logger.info(
                f"Pipeline {run_id} completed: {companies_saved} companies, {contacts_saved} contacts"
            )

        except PipelineCancelled:
            logger.info(f"Pipeline {run_id} cancelled by user")
            if cancelled_runs is not None:
                cancelled_runs.discard(run_id_str)

            try:
                await db.rollback()
            except Exception:
                pass

            try:
                result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
                run = result.scalar_one_or_none()
                if run:
                    run.status = "cancelled"
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
                logger.error(f"Failed to persist cancelled status for pipeline {run_id}: {commit_err}")

            _emit_event(events, run_id_str, {
                "type": "cancelled",
                "companies_found": run.companies_found or 0 if run else 0,
                "contacts_found": run.contacts_found or 0 if run else 0,
            })

        except Exception as e:
            logger.error(f"Pipeline {run_id} failed: {e}\n{traceback.format_exc()}")

            # Rollback any broken session state before updating status
            try:
                await db.rollback()
            except Exception:
                pass

            try:
                # Re-fetch the run to ensure we have a clean object
                result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
                run = result.scalar_one_or_none()
                if run:
                    run.status = "failed"
                    run.error_log = f"{str(e)}\n{traceback.format_exc()}"

                    # Persist collected logs even on failure
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
                logger.error(f"Failed to persist error status for pipeline {run_id}: {commit_err}")

            _emit_event(events, run_id_str, {
                "type": "error",
                "message": str(e),
            })


async def _process_company_phases_2_3(
    db,
    run_id: UUID,
    disc_company: dict,
    company_data: dict,
    icp: dict,
    events: dict,
    run_id_str: str,
    event_collector: list,
    company_index: int,
    total_companies: int,
    existing_company: "Company | None" = None,
    cancelled_runs: set = None,
    options: dict = None,
) -> tuple:
    """Run Phase 2 (contacts) + Phase 3 (BANT) for a single company.

    If existing_company is provided (multi-step resume), uses that DB row.
    Otherwise creates a new Company row (single-run mode).

    Returns (company, contacts_saved_count).
    """
    company_name = company_data.get("name", "Unknown")
    company_domain = company_data.get("website", "unknown")
    progress = 10 + int(80 * (company_index + 1) / total_companies)

    _emit_event(events, run_id_str, {
        "type": "company_start",
        "company_name": company_name,
        "company_index": company_index + 1,
        "total_companies": total_companies,
        "progress": progress,
    })

    logger.info(
        f"[Company {company_index+1}/{total_companies}] Starting: {company_name} ({company_domain})"
    )

    # ── Phase 2: Contact Agent ──
    _emit_event(events, run_id_str, {
        "type": "stage_update",
        "stage": "contact_discovery",
        "progress": progress,
        "message": f"Finding contacts for {company_name} ({company_index+1}/{total_companies})...",
    })

    contacts_saved = 0

    try:
        contact_callback = create_pipeline_callback_handler(
            events or {}, run_id_str, event_collector,
            initial_stage="contact_discovery",
            cancelled_runs=cancelled_runs,
        )
        contact_agent = create_contact_agent(callback_handler=contact_callback)
        contact_prompt = build_contact_prompt(disc_company, icp)

        contact_result = await asyncio.to_thread(contact_agent, contact_prompt)
        contact_json = parse_json_from_agent_result(contact_result)

        company_data["contacts"] = contact_json.get("contacts", [])
        company_data["research_data"] = contact_json.get("research_data", {})

        logger.info(
            f"[Company {company_index+1}/{total_companies}] Contact agent found "
            f"{len(company_data['contacts'])} contacts for {company_name}"
        )

    except PipelineCancelled:
        raise
    except Exception as contact_err:
        logger.warning(
            f"[Company {company_index+1}/{total_companies}] Contact agent failed for "
            f"{company_name}: {contact_err}. Saving Phase 1 data only."
        )
        company_data["contacts"] = []
        company_data["research_data"] = {}

    # ── Save/update Company + Contacts ──
    if existing_company:
        company = existing_company
    else:
        company = Company(
            pipeline_run_id=run_id,
            name=company_data.get("name", "Unknown"),
            website=company_data.get("website"),
            industry=company_data.get("industry"),
            sub_industry=company_data.get("sub_industry"),
            city=company_data.get("city"),
            state_region=company_data.get("state"),
            country=company_data.get("country"),
            employee_count=company_data.get("employee_count"),
            revenue_estimate=company_data.get("revenue_estimate"),
            tech_stack_json=company_data.get("tech_signals"),
            description=company_data.get("description"),
            source=company_data.get("source"),
            icp_match_score=company_data.get("icp_match_score"),
            match_reasoning=company_data.get("match_reasoning"),
            qualification=company_data.get("qualification", "good_fit"),
            raw_data_json=company_data.get("dimension_evidence"),
        )
        db.add(company)
        await db.flush()

    for contact_data in company_data.get("contacts", []):
        contact = Contact(
            company_id=company.id,
            full_name=contact_data.get("full_name"),
            first_name=contact_data.get("first_name"),
            last_name=contact_data.get("last_name"),
            designation=contact_data.get("designation"),
            role_category=contact_data.get("role_category"),
            email=contact_data.get("email"),
            phone=contact_data.get("phone"),
            linkedin_url=contact_data.get("linkedin_url"),
            source=contact_data.get("source"),
            confidence=contact_data.get("confidence"),
            enrichment_status=contact_data.get("enrichment_status", "pending"),
        )
        db.add(contact)
        contacts_saved += 1

    # ── Phase 3: BANT Agent ──
    _emit_event(events, run_id_str, {
        "type": "stage_update",
        "stage": "scoring",
        "progress": progress,
        "message": f"BANT scoring {company_name} ({company_index+1}/{total_companies})...",
    })

    try:
        bant_callback = create_pipeline_callback_handler(
            events or {}, run_id_str, event_collector,
            initial_stage="scoring",
            cancelled_runs=cancelled_runs,
        )
        bant_agent = create_bant_agent(callback_handler=bant_callback)
        bant_prompt = build_bant_prompt(company_data, icp)

        bant_result = await asyncio.to_thread(bant_agent, bant_prompt)
        bant_json = parse_json_from_agent_result(bant_result)

        bant_data = bant_json.get("bant_score", {})
        if bant_data:
            bant = BANTScore(
                company_id=company.id,
                budget_score=bant_data.get("budget_score"),
                budget_reason=bant_data.get("budget_reason"),
                budget_sources=bant_data.get("budget_sources"),
                authority_score=bant_data.get("authority_score"),
                authority_reason=bant_data.get("authority_reason"),
                authority_sources=bant_data.get("authority_sources"),
                need_score=bant_data.get("need_score"),
                need_reason=bant_data.get("need_reason"),
                need_sources=bant_data.get("need_sources"),
                timing_score=bant_data.get("timing_score"),
                timing_reason=bant_data.get("timing_reason"),
                timing_sources=bant_data.get("timing_sources"),
                total_score=_compute_weighted_bant_score(bant_data, options or {}),
                overall_summary=bant_data.get("overall_summary"),
            )
            db.add(bant)

        logger.info(
            f"[Company {company_index+1}/{total_companies}] BANT scoring complete for "
            f"{company_name}: total={bant_data.get('total_score', 'N/A')}"
        )

    except PipelineCancelled:
        raise
    except Exception as bant_err:
        logger.warning(
            f"[Company {company_index+1}/{total_companies}] BANT agent failed for "
            f"{company_name}: {bant_err}. Contacts already saved."
        )

    await db.flush()
    return company, contacts_saved


async def resume_pipeline_post_review(run_id: UUID, events: dict = None, cancelled_runs: set = None):
    """Resume a multi-step pipeline after the user has promoted companies.

    Runs Phase 2 (Contact Discovery) + Phase 3 (BANT Scoring) for promoted companies only.
    """
    run_id_str = str(run_id)

    async with async_session() as db:
        result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            logger.error(f"Pipeline run {run_id} not found for resume")
            return

        icp_result = await db.execute(
            select(ICPConfig).where(ICPConfig.id == run.icp_config_id)
        )
        icp_config = icp_result.scalar_one_or_none()
        if not icp_config:
            logger.error(f"ICP config {run.icp_config_id} not found for resume")
            return

        icp = icp_config.config_json
        options = run.options or {}
        event_collector = []

        try:
            run.status = "running"
            run.current_stage = "contact_discovery"
            await db.commit()

            # Fetch promoted companies
            promoted_result = await db.execute(
                select(Company).where(
                    Company.pipeline_run_id == run_id,
                    Company.promoted == True,
                )
            )
            promoted_companies = promoted_result.scalars().all()

            if not promoted_companies:
                logger.warning(f"No promoted companies found for run {run_id}")
                run.status = "completed"
                run.current_stage = "completed"
                run.completed_at = datetime.now(timezone.utc)
                await db.commit()
                _emit_event(events, run_id_str, {
                    "type": "completed",
                    "companies_found": run.companies_found or 0,
                    "contacts_found": 0,
                })
                return

            total_companies = len(promoted_companies)
            _emit_event(events, run_id_str, {
                "type": "stage_update",
                "stage": "contact_discovery",
                "progress": 35,
                "message": f"Phase 2-3: Researching {total_companies} promoted companies...",
            })

            contacts_saved = 0

            for i, company in enumerate(promoted_companies):
                disc_company = {
                    "name": company.name,
                    "website": company.website,
                    "industry": company.industry,
                    "sub_industry": company.sub_industry,
                    "city": company.city,
                    "state": company.state_region,
                    "country": company.country,
                    "employee_count": company.employee_count,
                    "revenue_estimate": company.revenue_estimate,
                    "description": company.description,
                    "tech_signals": company.tech_stack_json,
                    "icp_match_score": company.icp_match_score,
                    "match_reasoning": company.match_reasoning,
                    "qualification": company.qualification,
                    "source": company.source,
                }
                company_data = dict(disc_company)

                _, new_contacts = await _process_company_phases_2_3(
                    db=db,
                    run_id=run_id,
                    disc_company=disc_company,
                    company_data=company_data,
                    icp=icp,
                    events=events,
                    run_id_str=run_id_str,
                    event_collector=event_collector,
                    company_index=i,
                    total_companies=total_companies,
                    existing_company=company,
                    cancelled_runs=cancelled_runs,
                    options=options,
                )
                contacts_saved += new_contacts

            # Persist Phase 2-3 agent logs with offset sequence numbers
            existing_log_count_result = await db.execute(
                select(PipelineLog).where(PipelineLog.pipeline_run_id == run_id)
            )
            existing_log_count = len(existing_log_count_result.scalars().all())

            for seq, event_data in enumerate(event_collector):
                log = PipelineLog(
                    pipeline_run_id=run_id,
                    event_type=event_data.get("type", "unknown"),
                    event_data=event_data,
                    sequence_number=existing_log_count + seq,
                )
                db.add(log)

            # Mark completed
            run.status = "completed"
            run.current_stage = "completed"
            run.contacts_found = contacts_saved
            run.completed_at = datetime.now(timezone.utc)

            # Update stage_details with promotion results
            stage_details = run.stage_details or {}
            stage_details["promoted_count"] = total_companies
            stage_details["contacts_found"] = contacts_saved
            run.stage_details = stage_details
            await db.commit()

            # Generate embeddings for promoted companies that may not have them yet
            try:
                from app.services.embedding_service import embed_company
                for comp in promoted_companies:
                    if comp.embedding is None:
                        await embed_company(comp, db)
                await db.commit()
            except Exception as embed_err:
                logger.warning(f"Embedding generation failed (non-fatal): {embed_err}")

            _emit_event(events, run_id_str, {
                "type": "completed",
                "companies_found": run.companies_found or 0,
                "contacts_found": contacts_saved,
            })

            logger.info(
                f"Pipeline {run_id} resume completed: {total_companies} promoted companies, {contacts_saved} contacts"
            )

        except PipelineCancelled:
            logger.info(f"Pipeline resume {run_id} cancelled by user")
            if cancelled_runs is not None:
                cancelled_runs.discard(run_id_str)

            try:
                await db.rollback()
            except Exception:
                pass

            try:
                result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
                run = result.scalar_one_or_none()
                if run:
                    run.status = "cancelled"
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
                logger.error(f"Failed to persist cancelled status for pipeline resume {run_id}: {commit_err}")

            _emit_event(events, run_id_str, {
                "type": "cancelled",
                "companies_found": run.companies_found or 0 if run else 0,
                "contacts_found": run.contacts_found or 0 if run else 0,
            })

        except Exception as e:
            logger.error(f"Pipeline resume {run_id} failed: {e}\n{traceback.format_exc()}")

            try:
                await db.rollback()
            except Exception:
                pass

            try:
                result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
                run = result.scalar_one_or_none()
                if run:
                    run.status = "failed"
                    run.error_log = f"{str(e)}\n{traceback.format_exc()}"

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
                logger.error(f"Failed to persist error status for pipeline resume {run_id}: {commit_err}")

            _emit_event(events, run_id_str, {
                "type": "error",
                "message": str(e),
            })
