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
    contact_title: str | None = None,
    context: str | None = None,
    format: str = "email",
    tone: str = "direct",
    voice_profile: str = "concise",
    signal_id: str | None = None,
) -> str:
    """Generate a curated outreach draft for a company.

    Args:
        db: Database session
        company_kb_id: The company KB record ID
        contact_name: Optional specific contact to address
        contact_title: Optional contact job title
        context: Optional extra context (e.g. "focus on their recent funding")
        format: 'email' or 'linkedin'
        tone: 'direct', 'consultative', 'formal', 'casual'
        voice_profile: 'concise', 'consultative', 'formal'
        signal_id: Optional signal ID to anchor the outreach to

    Returns a markdown string with the outreach draft.
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

    # If a specific signal is referenced, fetch it and put it first
    anchor_signal = None
    if signal_id:
        from uuid import UUID as UUIDType
        try:
            anchor_result = await db.execute(
                select(SignalEvent).where(SignalEvent.id == UUIDType(signal_id))
            )
            anchor_signal = anchor_result.scalar_one_or_none()
        except Exception:
            pass

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

    signal_data = []
    if anchor_signal:
        signal_data.append({
            "type": anchor_signal.signal_type,
            "priority": anchor_signal.priority,
            "title": anchor_signal.title,
            "summary": anchor_signal.summary,
            "detected_at": anchor_signal.detected_at.isoformat() if anchor_signal.detected_at else None,
            "is_anchor": True,
        })
    for s in signals:
        if anchor_signal and str(s.id) == signal_id:
            continue
        signal_data.append({
            "type": s.signal_type,
            "priority": s.priority,
            "title": s.title,
            "summary": s.summary,
            "detected_at": s.detected_at.isoformat() if s.detected_at else None,
        })

    # Build the recipient line
    recipient = contact_name
    if not recipient and contact_data:
        recipient = contact_data[0].get("name")
    recipient_title = contact_title or (contact_data[0].get("title") if contact_data else None)
    if recipient:
        recipient_line = f"Address to: {recipient}" + (f", {recipient_title}" if recipient_title else "")
    else:
        recipient_line = "Use a generic professional greeting (do not invent a name)."

    extra_context = f"\nAdditional context from the user: {context}" if context else ""

    # Tone guidance
    tone_guidance = {
        "direct": "Be direct, get to the point quickly, no fluff.",
        "consultative": "Position yourself as a trusted advisor, lead with insights and value.",
        "formal": "Use professional, enterprise-grade language suitable for C-suite executives.",
        "casual": "Be warm and conversational, like messaging a professional acquaintance.",
    }.get(tone, "Professional but conversational.")

    # Voice guidance
    voice_guidance = {
        "concise": "Keep sentences short and punchy. No unnecessary words.",
        "consultative": "Use a value-led, advisory tone. Show you understand their challenges.",
        "formal": "Use complete, well-structured sentences. Professional and polished.",
    }.get(voice_profile, "Keep it concise.")

    # Anchor signal instruction
    anchor_instruction = ""
    if anchor_signal:
        anchor_instruction = f"""
## Anchor Signal (MUST reference in opening)
This outreach is triggered by a specific signal. You MUST reference this signal naturally in the opening paragraph:
- Type: {anchor_signal.signal_type}
- Title: {anchor_signal.title}
- Summary: {anchor_signal.summary or 'N/A'}
"""

    if format == "linkedin":
        prompt = f"""Generate a personalized LinkedIn connection/InMail message for B2B outreach.

## Company Data
{json.dumps(company_data, indent=2, default=str)}

## Key Contacts
{json.dumps(contact_data, indent=2, default=str) if contact_data else "No contacts discovered yet."}

## Recent Signals ({len(signal_data)} signals)
{json.dumps(signal_data, indent=2, default=str) if signal_data else "No recent signals."}
{anchor_instruction}
## Instructions
{recipient_line}
{extra_context}

## Tone: {tone}
{tone_guidance}

## Voice: {voice_profile}
{voice_guidance}

## Requirements for LinkedIn Message
1. **Opening**: Reference something specific about the person or company — a signal, shared connection, or recent news. No generic "I came across your profile."
2. **Value**: One clear sentence about what value you bring, connected to their situation.
3. **CTA**: Simple ask — a call, a resource, or just connecting.
4. **Length**: 80-120 words maximum. LinkedIn messages must be SHORT.
5. **No subject line needed** — this is a direct message.

## Output Format (just the message text, no markdown headers)

[Message body here]

---

**Why this approach works:**
[2-3 bullet points]

Generate the LinkedIn message now."""
    else:
        prompt = f"""Generate a professional, personalized outreach email for a B2B sales context.

## Company Data
{json.dumps(company_data, indent=2, default=str)}

## Key Contacts
{json.dumps(contact_data, indent=2, default=str) if contact_data else "No contacts discovered yet."}

## Recent Signals ({len(signal_data)} signals)
{json.dumps(signal_data, indent=2, default=str) if signal_data else "No recent signals detected."}
{anchor_instruction}
## Instructions
{recipient_line}
{extra_context}

## Tone: {tone}
{tone_guidance}

## Voice: {voice_profile}
{voice_guidance}

## Requirements
1. **Subject Line**: Compelling, specific to the company's situation. Not generic.
2. **Opening**: Reference a specific signal, news item, or company detail. Never start with "I hope this email finds you well."
3. **Value Prop**: Connect company signals to a specific pain point or opportunity.
4. **Social Proof**: Briefly reference similar companies or industries (don't fabricate).
5. **CTA**: Clear, low-friction call to action.
6. **Length**: 150-200 words max in the body.

## Output Format (Markdown)

**Subject:** [Your subject line here]

---

[Email body here]

---

**Why this approach works:**
[2-3 bullet points]

Generate the email now. Make it specific and compelling."""

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
