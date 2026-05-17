"""Account Brief Generator service.

Generates a one-page company briefing for pre-call preparation
by combining KB data, recent signals, and contacts into a
structured markdown document via Claude/Bedrock.
"""
import json
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_knowledge_base import CompanyKnowledgeBase
from app.models.signal_event import SignalEvent
from app.config import get_settings

logger = logging.getLogger(__name__)


async def generate_brief(
    db: AsyncSession,
    company_kb_id: UUID,
) -> str:
    """Generate an account brief for a company.

    Returns a markdown string with the full brief.
    """
    # Fetch KB record
    result = await db.execute(
        select(CompanyKnowledgeBase).where(CompanyKnowledgeBase.id == company_kb_id)
    )
    kb = result.scalar_one_or_none()
    if not kb:
        return "**Error:** Company not found in knowledge base."

    # Fetch recent signals
    signal_result = await db.execute(
        select(SignalEvent)
        .where(
            SignalEvent.company_kb_id == company_kb_id,
            SignalEvent.is_archived == False,
            SignalEvent.is_dismissed == False,
        )
        .order_by(SignalEvent.created_at.desc())
        .limit(10)
    )
    signals = list(signal_result.scalars().all())

    # Build context for the LLM
    company_data = {
        "name": kb.canonical_name,
        "domain": kb.normalized_domain,
        "industry": kb.industry,
        "sub_industry": kb.sub_industry,
        "country": kb.country,
        "city": kb.city,
        "state_region": kb.state_region,
        "employee_count": kb.employee_count,
        "revenue_estimate": kb.revenue_estimate,
        "tech_stack": kb.tech_stack_json,
        "description": kb.description,
        "best_final_score": kb.best_final_score,
        "best_deal_hotness_tier": kb.best_deal_hotness_tier,
        "contacts": kb.best_known_contacts or [],
        "times_discovered": kb.times_discovered,
        "last_enriched_at": kb.last_enriched_at.isoformat() if kb.last_enriched_at else None,
    }

    signal_data = [
        {
            "type": s.signal_type,
            "subtype": s.signal_subtype,
            "priority": s.priority,
            "title": s.title,
            "summary": s.summary,
            "detected_at": s.detected_at.isoformat() if s.detected_at else None,
            "source_url": s.source_url,
        }
        for s in signals
    ]

    prompt = f"""Generate a concise account briefing for a sales meeting. Use the company data and recent signals below.

## Company Data
{json.dumps(company_data, indent=2, default=str)}

## Recent Signals ({len(signal_data)} signals)
{json.dumps(signal_data, indent=2, default=str) if signal_data else "No recent signals detected."}

## Required Output Format (Markdown)

# Account Brief: [Company Name]

## Company Overview
A 2-3 sentence summary of who they are, what they do, and their market position.

## Key Metrics
| Metric | Value |
|--------|-------|
(Include: employees, revenue, industry, location, tech stack highlights)

## Recent Signals
(Bullet list of recent signals with dates and relevance. If no signals, state "No recent signals detected.")

## Key Stakeholders
(List known contacts with names, titles, and recommended approach for each)

## Talking Points
(3-5 specific talking points for the meeting, tied to the company's signals and needs)

## Recommended Approach
(2-3 sentences on how to position your offering based on the available data)

Keep it concise and actionable. Focus on what a sales rep needs to know in the next 5 minutes before a call."""

    # Call Bedrock/Claude
    try:
        brief = await _call_bedrock(prompt)
        return brief
    except Exception as e:
        logger.error(f"Brief generation failed: {e}")
        # Fallback: generate a simple brief from data
        return _generate_fallback_brief(kb, signals)


async def _call_bedrock(prompt: str) -> str:
    """Call AWS Bedrock Claude to generate the brief."""
    import asyncio
    import boto3

    settings = get_settings()

    def _invoke():
        client = boto3.client(
            "bedrock-runtime",
            region_name=settings.AWS_REGION,
        )
        response = client.converse(
            modelId=settings.BEDROCK_MODEL_ID,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 2000, "temperature": 0.3},
        )
        output = response.get("output", {})
        message = output.get("message", {})
        content = message.get("content", [])
        return content[0]["text"] if content else "Brief generation returned empty response."

    return await asyncio.to_thread(_invoke)


def _generate_fallback_brief(kb: CompanyKnowledgeBase, signals: list[SignalEvent]) -> str:
    """Generate a simple brief without LLM when Bedrock is unavailable."""
    lines = [f"# Account Brief: {kb.canonical_name or kb.normalized_domain}"]
    lines.append("")
    lines.append("## Company Overview")
    lines.append(kb.description or f"{kb.canonical_name} is a company in the {kb.industry or 'unknown'} industry.")
    lines.append("")

    lines.append("## Key Metrics")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    if kb.industry:
        lines.append(f"| Industry | {kb.industry} |")
    if kb.country:
        loc = ", ".join(filter(None, [kb.city, kb.state_region, kb.country]))
        lines.append(f"| Location | {loc} |")
    if kb.employee_count:
        lines.append(f"| Employees | {kb.employee_count:,} |")
    if kb.revenue_estimate:
        rev = kb.revenue_estimate
        rev_str = f"${rev/1e9:.1f}B" if rev >= 1e9 else f"${rev/1e6:.0f}M" if rev >= 1e6 else f"${rev:,}"
        lines.append(f"| Revenue | {rev_str} |")
    if kb.tech_stack_json:
        tech = kb.tech_stack_json if isinstance(kb.tech_stack_json, list) else []
        if tech:
            lines.append(f"| Tech Stack | {', '.join(tech[:8])} |")
    lines.append("")

    lines.append("## Recent Signals")
    if signals:
        for s in signals[:5]:
            date = s.detected_at.strftime("%b %d") if s.detected_at else ""
            lines.append(f"- **{s.signal_type.replace('_', ' ').title()}** ({date}): {s.title}")
    else:
        lines.append("No recent signals detected.")
    lines.append("")

    contacts = kb.best_known_contacts or []
    if contacts:
        lines.append("## Key Stakeholders")
        for c in contacts[:5]:
            name = c.get("full_name", "Unknown")
            title = c.get("designation", "")
            lines.append(f"- **{name}** — {title}")
    lines.append("")

    return "\n".join(lines)
