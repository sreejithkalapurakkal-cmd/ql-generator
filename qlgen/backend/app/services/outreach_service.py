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

# Outreach templates per signal type
OUTREACH_TEMPLATES = {
    "funding": {
        "hook_pattern": "I noticed {company} recently {event_summary}",
        "bridge": "Post-close is typically when teams begin evaluating infrastructure and vendor partnerships to support the next phase of growth.",
        "cta": "Would a 20-minute conversation be useful as you plan the next phase?",
    },
    "executive_change": {
        "hook_pattern": "I saw your appointment as {title} at {company}",
        "bridge": "Leaders in your position typically spend the first 90 days mapping the vendor landscape and identifying quick wins.",
        "cta": "Happy to share a quick framework — no sales deck, just context.",
    },
    "hiring_surge": {
        "hook_pattern": "I noticed {company} is building out the {department} team",
        "bridge": "Companies at your stage with similar hiring patterns often find that the right tooling early saves significant ramp-up time.",
        "cta": "Would you be open to a short call this week?",
    },
    "competitor_churn": {
        "hook_pattern": "I noticed {company} has been evaluating alternatives to {competitor}",
        "bridge": "Teams making this transition often find that the integration complexity is the deciding factor.",
        "cta": "I have a couple of specific examples I think would be relevant.",
    },
    "tech_adoption": {
        "hook_pattern": "I see {company} has recently adopted {technology}",
        "bridge": "Organizations making this kind of technology shift typically need complementary tooling to get the full value.",
        "cta": "Happy to share what we've seen work well alongside this stack.",
    },
    "partnership": {
        "hook_pattern": "Congratulations on the {company} partnership with {partner}",
        "bridge": "Strategic partnerships like this often create new operational requirements.",
        "cta": "Would it be helpful to discuss how similar companies have navigated this?",
    },
}

# Banned phrases that sound generic/spammy
BANNED_PHRASES = [
    "synergy", "synergies", "reach out", "circle back", "touch base",
    "game changer", "game-changer", "leverage", "paradigm shift",
    "disruptive", "bandwidth", "low-hanging fruit", "move the needle",
    "best-in-class", "thought leader", "deep dive", "at the end of the day",
    "win-win", "value-add", "take it to the next level", "on the same page",
    "think outside the box", "pivot", "scalable solution",
]


def detect_banned_phrases(text: str) -> list[str]:
    """Check for banned phrases in outreach text."""
    text_lower = text.lower()
    found = [phrase for phrase in BANNED_PHRASES if phrase in text_lower]
    return found


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
    variants: int = 1,
) -> dict:
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
        variants: Number of draft variants to generate (1-3)

    Returns a dict with drafts list, primary text, template info, and metadata.
    """
    # Fetch KB record
    result = await db.execute(
        select(CompanyKnowledgeBase).where(CompanyKnowledgeBase.id == company_kb_id)
    )
    kb = result.scalar_one_or_none()
    if not kb:
        error_text = "**Error:** Company not found in knowledge base."
        return {
            "drafts": [{"text": error_text, "variant": 1, "banned_phrases": []}],
            "primary": error_text,
            "template_used": None,
            "template_hint": None,
            "format": format,
            "tone": tone,
            "voice_profile": voice_profile,
        }

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
6. **Evidence-only**: Every fact about the company or contact must come from the provided data. Never fabricate details.

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
7. **Evidence-only**: Every claim about the company MUST reference data from the provided signals or company data. Never invent facts, statistics, or specifics not provided above.

## Output Format (Markdown)

**Subject:** [Your subject line here]

---

[Email body here]

---

**Why this approach works:**
[2-3 bullet points]

Generate the email now. Make it specific and compelling."""

    try:
        results = []
        for i in range(max(1, min(variants, 3))):
            variant_prompt = prompt
            if i > 0:
                variant_prompt += f"\n\nThis is variant #{i + 1}. Generate a DIFFERENT approach from previous variants. Use a different hook, different opening, and different CTA."
            draft_text = await _call_bedrock(variant_prompt)
            banned = detect_banned_phrases(draft_text)
            results.append({
                "text": draft_text,
                "variant": i + 1,
                "banned_phrases": banned,
            })

        # Get template hint if available
        template_hint = None
        if anchor_signal and anchor_signal.signal_type in OUTREACH_TEMPLATES:
            template_hint = OUTREACH_TEMPLATES[anchor_signal.signal_type]

        return {
            "drafts": results,
            "primary": results[0]["text"] if results else "",
            "template_used": anchor_signal.signal_type if anchor_signal else None,
            "template_hint": template_hint,
            "format": format,
            "tone": tone,
            "voice_profile": voice_profile,
        }
    except Exception as e:
        logger.error(f"Outreach draft generation failed: {e}")
        fallback = _generate_fallback_draft(kb, contacts, signals)
        return {
            "drafts": [{"text": fallback, "variant": 1, "banned_phrases": []}],
            "primary": fallback,
            "template_used": None,
            "template_hint": None,
            "format": format,
            "tone": tone,
            "voice_profile": voice_profile,
        }


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
