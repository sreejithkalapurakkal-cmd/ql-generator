"""Structured Research Brief Generator service.

Generates versioned, 8-section research briefs with inline citations,
confidence scoring, and source attribution. Each section follows the
Quantiv brief architecture:

1. Company Overview
2. Org Structure & Key Contacts
3. Recent Signals (Last 30 Days)
4. Competitive Landscape
5. Tech Stack & Infrastructure Signals
6. Budget & Spend Indicators
7. Why Now
8. Recommended Angle & Talk Tracks

Briefs are stored as BriefRevision records and are append-only (new
versions, never modified). They can be triggered manually or auto-generated
when high-confidence signals fire.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_knowledge_base import CompanyKnowledgeBase
from app.models.signal_event import SignalEvent
from app.models.brief_revision import BriefRevision
from app.config import get_settings

logger = logging.getLogger(__name__)

BRIEF_SECTIONS = [
    {"id": "overview", "heading": "Company Overview"},
    {"id": "org", "heading": "Org Structure & Key Contacts"},
    {"id": "signals", "heading": "Recent Signals (Last 30 Days)"},
    {"id": "competitive", "heading": "Competitive Landscape"},
    {"id": "tech", "heading": "Tech Stack & Infrastructure Signals"},
    {"id": "budget", "heading": "Budget & Spend Indicators"},
    {"id": "why-now", "heading": "Why Now"},
    {"id": "angle", "heading": "Recommended Angle & Talk Tracks"},
]


async def generate_structured_brief(
    db: AsyncSession,
    company_kb_id: UUID,
    trigger_signal_id: UUID | None = None,
    generated_by: str = "auto",
) -> BriefRevision | None:
    """Generate a structured 8-section research brief and save as new version.

    Returns the saved BriefRevision or None if the company was not found.
    """
    # Fetch KB record
    result = await db.execute(
        select(CompanyKnowledgeBase).where(CompanyKnowledgeBase.id == company_kb_id)
    )
    kb = result.scalar_one_or_none()
    if not kb:
        return None

    # Fetch recent signals
    signal_result = await db.execute(
        select(SignalEvent)
        .where(
            SignalEvent.company_kb_id == company_kb_id,
            SignalEvent.is_archived.is_(False),
            SignalEvent.is_dismissed.is_(False),
            SignalEvent.is_relevant.isnot(False),  # hide validator-rejected signals
        )
        .order_by(SignalEvent.created_at.desc())
        .limit(15)
    )
    signals = list(signal_result.scalars().all())

    # Get trigger signal headline if provided
    trigger_headline = None
    if trigger_signal_id:
        ts_result = await db.execute(
            select(SignalEvent.title).where(SignalEvent.id == trigger_signal_id)
        )
        trigger_headline = ts_result.scalar_one_or_none()

    # Determine next version number
    version_result = await db.execute(
        select(sa_func.coalesce(sa_func.max(BriefRevision.version), 0))
        .where(BriefRevision.company_kb_id == company_kb_id)
    )
    next_version = version_result.scalar() + 1

    # Build context and call LLM
    context = _build_brief_context(kb, signals)
    try:
        sections = await _generate_sections_via_llm(context)
    except Exception as e:
        logger.error(f"Brief generation failed for {company_kb_id}: {e}")
        sections = _generate_fallback_sections(kb, signals)

    # Count words
    word_count = sum(
        len(s.get("body", "").split()) + sum(len(b.split()) for b in s.get("bullets", []))
        for s in sections
    )

    # Save revision
    settings = get_settings()
    revision = BriefRevision(
        company_kb_id=company_kb_id,
        version=next_version,
        sections=sections,
        word_count=word_count,
        generated_by=generated_by,
        trigger_signal_id=trigger_signal_id,
        trigger_signal_headline=trigger_headline,
        model_id=settings.BEDROCK_MODEL_ID,
    )
    db.add(revision)

    # Update KB flags
    kb.has_brief = True
    kb.latest_brief_version = next_version

    await db.commit()
    await db.refresh(revision)

    logger.info(f"Brief v{next_version} generated for {kb.canonical_name} ({word_count} words)")

    # Emit event for cross-service reactions (notifications, cache invalidation)
    from app.events.event_bus import bus, Events
    await bus.emit(Events.BRIEF_GENERATED, {
        "company_kb_id": str(company_kb_id),
        "company_name": kb.canonical_name,
        "version": next_version,
    })

    return revision


async def get_latest_brief(
    db: AsyncSession,
    company_kb_id: UUID,
) -> BriefRevision | None:
    """Get the most recent brief revision for a company."""
    result = await db.execute(
        select(BriefRevision)
        .where(BriefRevision.company_kb_id == company_kb_id)
        .order_by(BriefRevision.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_brief_versions(
    db: AsyncSession,
    company_kb_id: UUID,
) -> list[BriefRevision]:
    """Get all brief revisions for a company, newest first."""
    result = await db.execute(
        select(BriefRevision)
        .where(BriefRevision.company_kb_id == company_kb_id)
        .order_by(BriefRevision.version.desc())
    )
    return list(result.scalars().all())


async def get_brief_by_version(
    db: AsyncSession,
    company_kb_id: UUID,
    version: int,
) -> BriefRevision | None:
    """Get a specific brief revision by version number."""
    result = await db.execute(
        select(BriefRevision)
        .where(
            BriefRevision.company_kb_id == company_kb_id,
            BriefRevision.version == version,
        )
    )
    return result.scalar_one_or_none()


# ─── LLM Generation ─────────────────────────────────────────────────────────


def _build_brief_context(kb: CompanyKnowledgeBase, signals: list[SignalEvent]) -> dict:
    """Build the context dict passed to the LLM for brief generation."""
    company = {
        "name": kb.canonical_name or kb.normalized_domain,
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
    }

    signal_list = []
    for s in signals:
        signal_list.append({
            "type": s.signal_type,
            "subtype": s.signal_subtype,
            "category": s.signal_category,
            "priority": s.priority,
            "strength": s.strength,
            "title": s.title,
            "summary": s.summary,
            "source_tool": s.source_tool,
            "source_url": s.source_url,
            "evidence_date": s.evidence_date.isoformat() if s.evidence_date else None,
            "detected_at": s.detected_at.isoformat() if s.detected_at else None,
        })

    return {"company": company, "signals": signal_list}


async def _generate_sections_via_llm(context: dict) -> list[dict]:
    """Call AWS Bedrock Claude to generate structured brief sections."""
    import boto3

    company = context["company"]
    signals = context["signals"]

    prompt = f"""You are a top-tier B2B sales research analyst. Generate a structured research brief for the company below.

## Company Data
{json.dumps(company, indent=2, default=str)}

## Recent Signals ({len(signals)} detected)
{json.dumps(signals, indent=2, default=str) if signals else "No signals detected yet."}

## Output Requirements

Return a JSON array of exactly 8 sections. Each section must follow this schema:
{{
    "id": "<section_id>",
    "heading": "<section heading>",
    "body": "<paragraph text with inline [N] citations referencing sources array>",
    "bullets": ["<key point 1>", "<key point 2>", ...],
    "sources": [
        {{"label": "<source title>", "source_class": "<SEC filing|Press release|Hiring signal|Web change|News article|LinkedIn|Financial data>", "url": "<url or null>", "date": "<date string or null>"}}
    ],
    "insufficient": <true if not enough data for this section>,
    "confidence": <float 0.0-1.0 section confidence>
}}

The 8 sections must be (in this order):
1. id="overview", heading="Company Overview" — Size, industry, key facts, public/private status
2. id="org", heading="Org Structure & Key Contacts" — Decision makers, reporting structure, procurement authority
3. id="signals", heading="Recent Signals (Last 30 Days)" — Detected signals with confidence and evidence
4. id="competitive", heading="Competitive Landscape" — Current vendor stack, evaluations, displacement opportunities
5. id="tech", heading="Tech Stack & Infrastructure Signals" — Technical environment, migration patterns
6. id="budget", heading="Budget & Spend Indicators" — Disclosed budgets, estimated spend capacity, procurement cycles
7. id="why-now", heading="Why Now" — Timing analysis, urgency windows, optimal outreach period
8. id="angle", heading="Recommended Angle & Talk Tracks" — Opening hooks, key messages, proof points, channels

## Citation Rules
- Use inline [N] references in the body text that correspond to the sources array (1-indexed).
- Only cite information you can attribute to a specific signal or data point.
- If a section lacks sufficient data, set "insufficient": true, provide a brief explanation in body, and leave bullets/sources empty.
- Set confidence based on evidence depth: 0.9+ for well-sourced, 0.5-0.8 for partial data, <0.5 for inference.

## Style
- Write like a seasoned sales strategist preparing an account executive for a call.
- Be specific and actionable. Avoid generic advice.
- The "Why Now" and "Recommended Angle" sections are the most valuable — make them excellent.
- Reference real data from the signals and company info. Never invent facts.

Return ONLY the JSON array. No markdown fences, no explanation."""

    settings = get_settings()

    def _invoke():
        client = boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)
        response = client.converse(
            modelId=settings.BEDROCK_MODEL_ID,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 8000, "temperature": 0.3},
        )
        output = response.get("output", {})
        message = output.get("message", {})
        content = message.get("content", [])
        return content[0]["text"] if content else "[]"

    raw = await asyncio.to_thread(_invoke)

    # Parse JSON from response (handle possible markdown fences)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    try:
        sections = json.loads(raw)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse brief JSON: {raw[:200]}")
        raise ValueError("Brief generation returned invalid JSON")

    # Validate structure
    if not isinstance(sections, list) or len(sections) == 0:
        raise ValueError("Brief generation returned empty sections")

    # Ensure all 8 sections are present, fill missing ones
    section_ids = {s["id"] for s in sections}
    for template in BRIEF_SECTIONS:
        if template["id"] not in section_ids:
            sections.append({
                "id": template["id"],
                "heading": template["heading"],
                "body": "",
                "bullets": [],
                "sources": [],
                "insufficient": True,
                "confidence": 0.0,
            })

    # Sort by canonical order
    order = {s["id"]: i for i, s in enumerate(BRIEF_SECTIONS)}
    sections.sort(key=lambda s: order.get(s["id"], 99))

    return sections


# ─── Fallback Generation ────────────────────────────────────────────────────


def _generate_fallback_sections(kb: CompanyKnowledgeBase, signals: list[SignalEvent]) -> list[dict]:
    """Generate structured sections from data alone when LLM is unavailable."""
    name = kb.canonical_name or kb.normalized_domain
    sections = []

    # Overview
    emp = f"{kb.employee_count:,}" if kb.employee_count else "unknown"
    rev_str = ""
    if kb.revenue_estimate:
        r = kb.revenue_estimate
        rev_str = f"${r/1e9:.1f}B" if r >= 1e9 else f"${r/1e6:.0f}M" if r >= 1e6 else f"${r:,}"

    overview_body = kb.description or f"{name} is a company in the {kb.industry or 'unknown'} industry."
    overview_bullets = [b for b in [
        f"{emp} employees" if kb.employee_count else None,
        kb.industry,
        rev_str or None,
        ", ".join(filter(None, [kb.city, kb.state_region, kb.country])) or None,
    ] if b]

    sections.append({
        "id": "overview", "heading": "Company Overview",
        "body": overview_body, "bullets": overview_bullets,
        "sources": [], "insufficient": False, "confidence": 0.6,
    })

    # Org
    contacts = kb.best_known_contacts or []
    if contacts:
        org_bullets = [f"{c.get('full_name', 'Unknown')} — {c.get('designation', '')}" for c in contacts[:5]]
        sections.append({
            "id": "org", "heading": "Org Structure & Key Contacts",
            "body": f"Key stakeholders identified at {name}.",
            "bullets": org_bullets, "sources": [], "insufficient": False, "confidence": 0.5,
        })
    else:
        sections.append({
            "id": "org", "heading": "Org Structure & Key Contacts",
            "body": "", "bullets": [], "sources": [], "insufficient": True, "confidence": 0.0,
        })

    # Signals
    if signals:
        sig_bullets = []
        for s in signals[:5]:
            date_str = s.evidence_date.strftime("%b %d, %Y") if s.evidence_date else (
                s.detected_at.strftime("%b %d, %Y") if s.detected_at else "")
            sig_bullets.append(f"{s.signal_type.replace('_', ' ').title()} ({date_str}): {s.title}")
        sections.append({
            "id": "signals", "heading": "Recent Signals (Last 30 Days)",
            "body": f"{len(signals)} signal(s) detected for {name}.",
            "bullets": sig_bullets, "sources": [], "insufficient": False, "confidence": 0.7,
        })
    else:
        sections.append({
            "id": "signals", "heading": "Recent Signals (Last 30 Days)",
            "body": "No signals detected in the monitoring window.",
            "bullets": [], "sources": [], "insufficient": True, "confidence": 0.0,
        })

    # Remaining sections — insufficient data without LLM
    for sid, heading in [
        ("competitive", "Competitive Landscape"),
        ("tech", "Tech Stack & Infrastructure Signals"),
        ("budget", "Budget & Spend Indicators"),
        ("why-now", "Why Now"),
        ("angle", "Recommended Angle & Talk Tracks"),
    ]:
        body = ""
        bullets = []
        insufficient = True
        confidence = 0.0

        if sid == "tech" and kb.tech_stack_json:
            tech = kb.tech_stack_json if isinstance(kb.tech_stack_json, list) else []
            if tech:
                body = f"Known technology stack for {name}."
                bullets = tech[:8]
                insufficient = False
                confidence = 0.4

        sections.append({
            "id": sid, "heading": heading,
            "body": body, "bullets": bullets,
            "sources": [], "insufficient": insufficient, "confidence": confidence,
        })

    return sections


# ─── Legacy compatibility ────────────────────────────────────────────────────


async def generate_brief(db: AsyncSession, company_kb_id: UUID) -> str:
    """Legacy function — generates a brief and returns markdown string.

    Preserved for backward compatibility with existing briefs.py API route.
    """
    revision = await generate_structured_brief(db, company_kb_id, generated_by="manual")
    if not revision:
        return "**Error:** Company not found in knowledge base."

    # Convert structured sections to markdown
    lines = []
    name = "Account"
    for section in revision.sections:
        heading = section.get("heading", "")
        body = section.get("body", "")
        bullets = section.get("bullets", [])
        insufficient = section.get("insufficient", False)

        if section["id"] == "overview":
            # Extract name from first section
            name = heading

        lines.append(f"## {heading}")
        if insufficient:
            lines.append("_Insufficient data — this section will populate as signals are detected._")
        else:
            if body:
                # Strip citation markers for markdown output
                import re
                clean_body = re.sub(r'\[\d+\]', '', body)
                lines.append(clean_body)
            for b in bullets:
                lines.append(f"- {b}")
        lines.append("")

    return f"# Research Brief: {name}\n\n" + "\n".join(lines)
