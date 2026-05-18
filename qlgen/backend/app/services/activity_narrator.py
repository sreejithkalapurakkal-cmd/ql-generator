"""Activity Narrator — template-based event-to-narration engine.

Transforms raw tool/agent events into human-friendly research narration.
Used by the research orchestrator, signal service, and correlation engine
to auto-generate ActivityEvent records.
"""
import logging
from datetime import datetime, timezone
from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from app.models.activity_event import ActivityEvent

logger = logging.getLogger(__name__)

# Signal type → human-friendly label
SIGNAL_TYPE_HUMAN = {
    "funding": "new funding activity",
    "hiring_surge": "rapid expansion in hiring",
    "executive_change": "executive leadership change",
    "champion_job_change": "former champion at new company",
    "tech_adoption": "new technology adoption",
    "tech_removal": "technology stack change",
    "product_launch": "product or feature launch",
    "earnings_report": "earnings disclosure",
    "press_mention": "press coverage",
    "partnership": "strategic partnership",
    "expansion": "geographic or operational expansion",
    "web_change": "website content update",
    "sec_filing": "regulatory filing",
    "budget_signal": "budget indicator",
    "urgency_signal": "urgency indicator",
    "custom_signal": "custom signal match",
    "competitor_adoption": "competitor technology adoption",
    "competitor_churn": "competitor customer churn",
}

# Event templates: event_type → {narrative, detail, category, milestone, verbosity}
TEMPLATES = {
    # Research lifecycle
    "research_start": {
        "narrative": "Starting {depth} research for {company_name}",
        "category": "research",
        "milestone": True,
        "verbosity": "summary",
    },
    "research_complete": {
        "narrative": "Research complete for {company_name}: {signals_found} signals detected",
        "category": "research",
        "milestone": True,
        "verbosity": "summary",
    },
    "research_failed": {
        "narrative": "Research failed for {company_name}: {error}",
        "category": "research",
        "milestone": True,
        "verbosity": "summary",
    },

    # Tool calls
    "tool_call.tavily_search": {
        "narrative": "Searching for {query_summary} across news and press sources",
        "detail": "Querying Tavily API for '{query}' — {result_count} results",
        "category": "research",
        "verbosity": "detailed",
    },
    "tool_call.exa_search": {
        "narrative": "Running AI-powered search for {query_summary}",
        "detail": "Querying Exa API for '{query}' — {result_count} results",
        "category": "research",
        "verbosity": "detailed",
    },
    "tool_call.apollo_search": {
        "narrative": "Looking up hiring activity and employee data for {company_name}",
        "detail": "Apollo API query for {company_name}",
        "category": "research",
        "verbosity": "detailed",
    },
    "tool_call.sec_search": {
        "narrative": "Scanning SEC filings for budget disclosures",
        "detail": "Querying SEC EDGAR for {company_name}",
        "category": "research",
        "verbosity": "detailed",
    },
    "tool_call.linkedin_search": {
        "narrative": "Searching LinkedIn for executive profiles at {company_name}",
        "category": "research",
        "verbosity": "detailed",
    },
    "tool_call.web_scraper": {
        "narrative": "Crawling {url} for intelligence",
        "category": "research",
        "verbosity": "technical",
    },
    "tool_call.generic": {
        "narrative": "Running {tool_name} for {company_name}",
        "category": "research",
        "verbosity": "technical",
    },

    # Signal events
    "signal.detected": {
        "narrative": "Detected {signal_type_human}: {signal_title}",
        "detail": "Confidence: {confidence} | Strength: {strength}/100 | Source: {source_class}",
        "category": "signal",
        "milestone": True,
        "verbosity": "summary",
    },
    "signal.verified": {
        "narrative": "Verified signal against {source_count} independent sources — confidence {direction} to {confidence}",
        "category": "signal",
        "milestone": True,
        "verbosity": "summary",
    },
    "signal.dismissed": {
        "narrative": "Signal dismissed: {signal_title}",
        "category": "signal",
        "verbosity": "detailed",
    },

    # Correlation events
    "correlation.found": {
        "narrative": "Correlating {signal_a} with {signal_b} — {correlation_insight}",
        "detail": "Pattern: {pattern_name}, boost factor: {boost_factor}",
        "category": "signal",
        "milestone": True,
        "verbosity": "summary",
    },

    # Synthesis events
    "synthesis.section_started": {
        "narrative": "Generating research brief section: {section_name}",
        "category": "synthesis",
        "verbosity": "detailed",
    },
    "synthesis.section_complete": {
        "narrative": "Completed brief section: {section_name}",
        "category": "synthesis",
        "verbosity": "detailed",
    },
    "synthesis.brief_ready": {
        "narrative": "Research brief v{version} ready — {word_count} words, {section_count} sections",
        "category": "synthesis",
        "milestone": True,
        "verbosity": "summary",
    },

    # Contact events
    "contact.found": {
        "narrative": "Identified {contact_name} ({contact_title}) as {influence_level}",
        "category": "contact",
        "verbosity": "detailed",
    },
    "contact.enrichment_complete": {
        "narrative": "Contact enrichment complete — {count} decision makers identified",
        "category": "contact",
        "milestone": True,
        "verbosity": "summary",
    },

    # Outreach events
    "outreach.draft_generated": {
        "narrative": "Generated {format} draft for {contact_name} anchored to {signal_title}",
        "category": "outreach",
        "verbosity": "detailed",
    },
    "outreach.sent": {
        "narrative": "Outreach marked as sent to {contact_name}",
        "category": "outreach",
        "milestone": True,
        "verbosity": "summary",
    },

    # Heat score events
    "heat.updated": {
        "narrative": "Signal heat score updated: {old_score} → {new_score} ({delta:+.0f})",
        "category": "signal",
        "verbosity": "detailed",
    },

    # Source events
    "source.crawled": {
        "narrative": "Crawled {source_name} — {change_summary}",
        "category": "research",
        "verbosity": "detailed",
    },
    "source.changed": {
        "narrative": "Changes detected on {source_name}: {change_summary}",
        "category": "research",
        "milestone": True,
        "verbosity": "summary",
    },
}


class ActivityNarrator:
    """Converts technical events into user-friendly research narration."""

    def narrate(
        self,
        event_type: str,
        context: dict,
        research_job_id: UUID | None = None,
        company_kb_id: UUID | None = None,
        confidence: float | None = None,
    ) -> ActivityEvent:
        """Convert a raw event into a narrated ActivityEvent.

        Args:
            event_type: The event type key (e.g., "signal.detected")
            context: Dict with template variables
            research_job_id: Optional link to research job
            company_kb_id: Optional link to company
            confidence: Optional confidence score

        Returns:
            An ActivityEvent model instance (not yet added to session)
        """
        template = TEMPLATES.get(event_type, TEMPLATES.get("tool_call.generic", {}))

        # Resolve signal_type_human if present
        if "signal_type" in context and "signal_type_human" not in context:
            context["signal_type_human"] = SIGNAL_TYPE_HUMAN.get(
                context["signal_type"], context["signal_type"].replace("_", " ")
            )

        # Format narrative
        narrative = self._format(template.get("narrative", event_type), context)
        narrative_detail = self._format(template.get("detail"), context) if template.get("detail") else None

        return ActivityEvent(
            research_job_id=research_job_id,
            company_kb_id=company_kb_id,
            event_type=event_type,
            event_category=template.get("category", "research"),
            narrative=narrative,
            narrative_detail=narrative_detail,
            technical_detail=context if template.get("verbosity") == "technical" else None,
            confidence=confidence,
            milestone=template.get("milestone", False),
            verbosity_level=template.get("verbosity", "detailed"),
        )

    def _format(self, template: str | None, context: dict) -> str:
        """Safe string format — missing keys are left as placeholders."""
        if not template:
            return ""
        try:
            return template.format(**{k: v for k, v in context.items() if v is not None})
        except (KeyError, IndexError, ValueError):
            # Fallback: replace what we can
            result = template
            for key, val in context.items():
                if val is not None:
                    result = result.replace(f"{{{key}}}", str(val))
            return result


# Module-level singleton
narrator = ActivityNarrator()


async def narrate_and_save(
    db: AsyncSession,
    event_type: str,
    context: dict,
    research_job_id: UUID | None = None,
    company_kb_id: UUID | None = None,
    confidence: float | None = None,
) -> ActivityEvent:
    """Create a narrated activity event and add it to the session."""
    event = narrator.narrate(
        event_type=event_type,
        context=context,
        research_job_id=research_job_id,
        company_kb_id=company_kb_id,
        confidence=confidence,
    )
    db.add(event)
    await db.flush()
    return event
