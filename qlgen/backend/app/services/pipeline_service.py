import json
import logging
import traceback
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.lead_gen_agent import create_lead_gen_agent
from app.agent.prompt_builder import build_pipeline_prompt
from app.db.session import async_session
from app.models.pipeline import PipelineRun
from app.models.icp import ICPConfig
from app.models.company import Company
from app.models.contact import Contact
from app.models.bant import BANTScore

logger = logging.getLogger(__name__)


def _emit_event(events: dict, run_id: str, event: dict):
    """Add event to the SSE event list."""
    if events is not None and run_id in events:
        events[run_id].append(event)


def parse_json_from_agent_result(result) -> dict:
    """Extract JSON from the agent's text response."""
    text = str(result)

    # Try to find JSON block in markdown code fence
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        text = text[start:end].strip()

    # Try to find JSON object
    if "{" in text:
        start = text.index("{")
        depth = 0
        for i, char in enumerate(text[start:], start):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    text = text[start : i + 1]
                    break

    return json.loads(text)


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
                "progress": 10,
                "message": "Starting company discovery...",
            })

            # Create agent and execute
            logger.info(f"Creating agent for pipeline run {run_id}")
            agent = create_lead_gen_agent()
            prompt = build_pipeline_prompt(icp, options)

            _emit_event(events, run_id_str, {
                "type": "stage_update",
                "stage": "company_discovery",
                "progress": 20,
                "message": "Agent is searching for companies matching ICP...",
            })

            # Single agent call — handles all 4 stages
            logger.info(f"Invoking agent for pipeline run {run_id}")
            result = agent(prompt)
            logger.info(f"Agent completed for pipeline run {run_id}")

            _emit_event(events, run_id_str, {
                "type": "stage_update",
                "stage": "scoring",
                "progress": 80,
                "message": "Agent completed. Parsing results...",
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
                        authority_score=bant_data.get("authority_score"),
                        authority_reason=bant_data.get("authority_reason"),
                        need_score=bant_data.get("need_score"),
                        need_reason=bant_data.get("need_reason"),
                        timing_score=bant_data.get("timing_score"),
                        timing_reason=bant_data.get("timing_reason"),
                        total_score=bant_data.get("total_score"),
                        overall_summary=bant_data.get("overall_summary"),
                    )
                    db.add(bant)

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
            await db.commit()

            _emit_event(events, run_id_str, {
                "type": "error",
                "message": str(e),
            })
