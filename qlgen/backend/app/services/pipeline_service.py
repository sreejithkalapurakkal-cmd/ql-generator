import asyncio
import json
import logging
import traceback
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.lead_gen_agent import create_lead_gen_agent, create_pipeline_callback_handler
from app.agent.prompt_builder import build_pipeline_prompt
from app.db.session import async_session
from app.models.pipeline import PipelineRun
from app.models.icp import ICPConfig
from app.models.company import Company
from app.models.contact import Contact
from app.models.bant import BANTScore
from app.models.pipeline_log import PipelineLog

logger = logging.getLogger(__name__)


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


async def execute_pipeline(run_id: UUID, events: dict = None):
    """Main pipeline execution."""
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
                "message": "Initializing agent...",
            })

            # Create agent with callback handler for real-time progress
            logger.info(f"Creating agent for pipeline run {run_id}")
            event_collector = []
            callback_handler = None
            if events is not None:
                callback_handler = create_pipeline_callback_handler(events, run_id_str, event_collector)
            else:
                callback_handler = create_pipeline_callback_handler({}, run_id_str, event_collector)
            agent = create_lead_gen_agent(callback_handler=callback_handler)
            prompt = build_pipeline_prompt(icp, options)

            # Single agent call — handles all 4 stages
            # The callback handler emits granular tool_start, agent_reasoning, and stage_update events
            # IMPORTANT: agent() is synchronous — run in thread pool so the event loop
            # remains free to yield SSE events in real-time
            logger.info(f"Invoking agent for pipeline run {run_id}")
            result = await asyncio.to_thread(agent, prompt)
            logger.info(f"Agent completed for pipeline run {run_id}")
            result_text = str(result)
            logger.info(f"Agent result type: {type(result).__name__}, text length: {len(result_text)}, first 500 chars: {result_text[:500]}")

            _emit_event(events, run_id_str, {
                "type": "stage_update",
                "stage": "completed",
                "progress": 90,
                "message": "Agent completed. Parsing and saving results...",
            })

            # Parse the agent's JSON output
            result_json = parse_json_from_agent_result(result)

            # Save results to database
            companies_saved = 0
            contacts_saved = 0

            for company_data in result_json.get("companies", []):
                company = Company(
                    pipeline_run_id=run_id,
                    name=company_data.get("name", "Unknown"),
                    website=company_data.get("website"),
                    industry=company_data.get("industry"),
                    city=company_data.get("city"),
                    state_region=company_data.get("state"),
                    country=company_data.get("country"),
                    employee_count=company_data.get("employee_count"),
                    revenue_estimate=company_data.get("revenue_estimate"),
                    tech_stack_json=company_data.get("tech_signals"),
                    source=company_data.get("source"),
                    icp_match_score=company_data.get("icp_match_score"),
                    match_reasoning=company_data.get("match_reasoning"),
                    qualification="qualified",
                )
                db.add(company)
                await db.flush()
                companies_saved += 1

                # Save contacts
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

                # Save BANT score
                bant_data = company_data.get("bant_score")
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
                        total_score=bant_data.get("total_score"),
                        overall_summary=bant_data.get("overall_summary"),
                    )
                    db.add(bant)

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

            _emit_event(events, run_id_str, {
                "type": "completed",
                "companies_found": companies_saved,
                "contacts_found": contacts_saved,
            })

            logger.info(
                f"Pipeline {run_id} completed: {companies_saved} companies, {contacts_saved} contacts"
            )

        except Exception as e:
            logger.error(f"Pipeline {run_id} failed: {e}\n{traceback.format_exc()}")
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

            _emit_event(events, run_id_str, {
                "type": "error",
                "message": str(e),
            })
