"""Outreach Email Draft Generator service.

Generates a curated outreach email for a tracked company by combining
KB data, recent signals, contacts, and tracking list signal hints
into a personalized email via Claude/Bedrock.
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


async def generate_outreach_draft(
    db: AsyncSession,
    company_kb_id: UUID,
    contact_name: str | None = None,
    context: str | None = None,
) -> str:
    """Generate a curated outreach email draft for a company.

    Args:
        db: Database session
        company_kb_id: The company KB record ID
        contact_name: Optional specific contact to address
        context: Optional extra context (e.g. "focus on their recent funding")

    Returns a markdown string with the outreach email.
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
        "employee_count": kb.employee_count,
        "revenue_estimate": kb.revenue_estimate,
        "tech_stack": kb.tech_stack_json,
        "description": kb.description,
    }

    contacts = kb.best_known_contacts or []
    contact_data = [
        {
            "name": c.get("full_name"),
            "title": c.get("designation"),
            "email": c.get("email"),
            "linkedin": c.get("linkedin_url"),
        }
        for c in contacts[:5]
    ]

    signal_data = [
        {
            "type": s.signal_type,
            "priority": s.priority,
            "title": s.title,
            "summary": s.summary,
            "detected_at": s.detected_at.isoformat() if s.detected_at else None,
        }
        for s in signals
    ]

    # Build the recipient line
    recipient = contact_name
    if not recipient and contact_data:
        recipient = contact_data[0].get("name")
    recipient_line = f"Address the email to: {recipient}" if recipient else "Use a generic professional greeting (do not invent a name)."

    extra_context = f"\nAdditional context from the user: {context}" if context else ""

    prompt = f"""Generate a professional, personalized outreach email for a B2B sales context. Use the company data, recent signals, and contact info below to craft a highly relevant and compelling email.

## Company Data
{json.dumps(company_data, indent=2, default=str)}

## Key Contacts
{json.dumps(contact_data, indent=2, default=str) if contact_data else "No contacts discovered yet."}

## Recent Signals ({len(signal_data)} signals)
{json.dumps(signal_data, indent=2, default=str) if signal_data else "No recent signals detected."}

## Instructions
{recipient_line}
{extra_context}

## Requirements
1. **Subject Line**: Compelling, specific to the company's situation. Not generic.
2. **Opening**: Reference a specific signal, news item, or company detail that shows you've done your homework. Never start with "I hope this email finds you well" or similar cliches.
3. **Value Prop**: Connect what you know about the company (signals, industry, tech stack) to a specific pain point or opportunity. Be specific, not generic.
4. **Social Proof**: If applicable, briefly reference similar companies or industries (but don't fabricate names).
5. **CTA**: A clear, low-friction call to action (e.g., a 15-minute call, sharing a case study).
6. **Tone**: Professional but conversational. No buzzwords or jargon. Write like a knowledgeable peer, not a sales robot.
7. **Length**: Keep it concise — 150-200 words max in the body.

## Output Format (Markdown)

**Subject:** [Your subject line here]

---

[Email body here]

---

**Why this approach works:**
[2-3 bullet points explaining the personalization strategy and which signals/data points were leveraged]

Generate the email now. Make it specific and compelling — this is a real prospect."""

    try:
        draft = await _call_bedrock(prompt)
        return draft
    except Exception as e:
        logger.error(f"Outreach draft generation failed: {e}")
        return _generate_fallback_draft(kb, contacts, signals)


async def _call_bedrock(prompt: str) -> str:
    """Call AWS Bedrock Claude to generate the outreach email."""
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
            inferenceConfig={"maxTokens": 1500, "temperature": 0.5},
        )
        output = response.get("output", {})
        message = output.get("message", {})
        content = message.get("content", [])
        return content[0]["text"] if content else "Draft generation returned empty response."

    return await asyncio.to_thread(_invoke)


def _generate_fallback_draft(
    kb: CompanyKnowledgeBase,
    contacts: list[dict],
    signals: list,
) -> str:
    """Generate a simple template when Bedrock is unavailable."""
    name = kb.canonical_name or kb.normalized_domain or "there"
    contact_name = contacts[0].get("full_name") if contacts else None
    greeting = f"Hi {contact_name.split()[0]}," if contact_name else f"Hi,"

    lines = []
    lines.append(f"**Subject:** Reaching out to {name}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(greeting)
    lines.append("")

    if signals:
        s = signals[0]
        lines.append(f"I noticed {name} recently {s.title.lower() if s.title else 'had some interesting developments'}. "
                      f"That caught my attention because it often signals an opportunity to improve outcomes in this area.")
    else:
        lines.append(f"I've been researching companies in the {kb.industry or 'your'} space and {name} stood out.")

    lines.append("")
    lines.append("I'd love to share how we've helped similar companies and explore whether there's a fit.")
    lines.append("")
    lines.append("Would you be open to a quick 15-minute call this week?")
    lines.append("")
    lines.append("Best regards")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**Why this approach works:**")
    lines.append("- Fallback template generated (AI service temporarily unavailable)")
    lines.append("- Customize the subject line and opening with specific company details")

    return "\n".join(lines)
