"""Signal detection and scoring service.

Detects signals for tracked companies by calling existing tools directly
(no agent overhead). Computes composite signal heat scores with decay.

Supports user-provided signal hints (budget signals, urgency signals,
custom hints) that guide search queries for more targeted detection.
"""
import asyncio
import logging
import math
from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal_event import SignalEvent
from app.models.company_knowledge_base import CompanyKnowledgeBase
from app.models.tracking_list_membership import TrackingListMembership
from app.services.search_helpers import resilient_search

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# Signal type configuration
# ──────────────────────────────────────────────────────────────────

SIGNAL_CONFIG: dict[str, dict] = {
    "funding": {
        "category": "financial",
        "half_life_days": 2,
        "cold_days": 14,
        "default_weight": 1.5,
    },
    "hiring_surge": {
        "category": "personnel",
        "half_life_days": 14,
        "cold_days": 60,
        "default_weight": 1.0,
    },
    "executive_change": {
        "category": "personnel",
        "half_life_days": 7,
        "cold_days": 30,
        "default_weight": 1.3,
    },
    "champion_job_change": {
        "category": "personnel",
        "half_life_days": 7,
        "cold_days": 30,
        "default_weight": 1.8,
    },
    "tech_adoption": {
        "category": "product",
        "half_life_days": 30,
        "cold_days": 120,
        "default_weight": 0.8,
    },
    "product_launch": {
        "category": "product",
        "half_life_days": 3,
        "cold_days": 21,
        "default_weight": 1.0,
    },
    "earnings_report": {
        "category": "financial",
        "half_life_days": 1,
        "cold_days": 7,
        "default_weight": 0.7,
    },
    "press_mention": {
        "category": "event",
        "half_life_days": 3,
        "cold_days": 14,
        "default_weight": 0.5,
    },
    "partnership": {
        "category": "event",
        "half_life_days": 7,
        "cold_days": 30,
        "default_weight": 1.0,
    },
    "expansion": {
        "category": "event",
        "half_life_days": 14,
        "cold_days": 60,
        "default_weight": 1.0,
    },
    "competitor_adoption": {
        "category": "intent",
        "half_life_days": 7,
        "cold_days": 30,
        "default_weight": 1.2,
    },
    "competitor_churn": {
        "category": "intent",
        "half_life_days": 3,
        "cold_days": 14,
        "default_weight": 1.5,
    },
    # Hint-driven signal types
    "budget_signal": {
        "category": "financial",
        "half_life_days": 7,
        "cold_days": 30,
        "default_weight": 1.4,
    },
    "urgency_signal": {
        "category": "intent",
        "half_life_days": 5,
        "cold_days": 21,
        "default_weight": 1.5,
    },
    "custom_signal": {
        "category": "event",
        "half_life_days": 7,
        "cold_days": 30,
        "default_weight": 1.0,
    },
}

# Default signal types for on-demand detection
DEFAULT_SIGNAL_TYPES = [
    "funding", "hiring_surge", "executive_change",
    "product_launch", "press_mention", "partnership",
]


# ──────────────────────────────────────────────────────────────────
# Signal detection (direct tool calls)
# ──────────────────────────────────────────────────────────────────

async def detect_signals_for_company(
    db: AsyncSession,
    company_kb_id: UUID,
    signal_types: list[str] | None = None,
    signal_hints: dict | None = None,
    event_emitter=None,
) -> list[SignalEvent]:
    """Detect signals for a single company by calling tools directly.

    Args:
        signal_hints: Optional dict with keys:
            - budget_signals: list[str] — e.g. ["cloud migration budget", "Series B funding"]
            - urgency_signals: list[str] — e.g. ["regulatory compliance deadline", "tech migration"]
            - custom_hints: list[str] — e.g. ["Kubernetes adoption", "AI/ML investment"]
            - target_roles: list[str] — ignored here, used by enrichment service
        event_emitter: Optional async callable(event_type: str, data: dict) for
            emitting granular progress events (tool_start, tool_result, signal_found).

    Returns a list of newly created SignalEvent records.
    """
    result = await db.execute(
        select(CompanyKnowledgeBase).where(CompanyKnowledgeBase.id == company_kb_id)
    )
    kb = result.scalar_one_or_none()
    if not kb:
        return []

    raw_name = kb.canonical_name or kb.normalized_domain
    domain = kb.normalized_domain or ""
    # Use clean company name for all searches (not "snowflake.com" but "Snowflake")
    company_name = _clean_company_name(raw_name, domain)
    types_to_check = signal_types or DEFAULT_SIGNAL_TYPES
    hints = signal_hints or {}

    async def _emit(event_type: str, data: dict):
        if event_emitter:
            await event_emitter(event_type, data)

    new_signals: list[SignalEvent] = []

    # Standard signal detection
    for signal_type in types_to_check:
        label = signal_type.replace("_", " ").title()
        await _emit("tool_start", {
            "tool": signal_type,
            "label": f"Checking {label}...",
            "company_name": company_name,
        })
        try:
            detected = await _detect_single_signal(
                signal_type, company_name, domain, kb,
            )
            saved = await _save_signals(db, company_kb_id, signal_type, detected, company_name)
            await _emit("tool_result", {
                "tool": signal_type,
                "label": label,
                "results_count": len(detected),
                "signals_saved": len(saved),
                "company_name": company_name,
            })
            for s in saved:
                await _emit("signal_found", {
                    "signal_type": s.signal_type,
                    "title": s.title[:200] if s.title else "",
                    "priority": s.priority,
                    "company_name": company_name,
                })
            new_signals.extend(saved)
        except Exception as e:
            logger.warning(f"Signal detection '{signal_type}' failed for {company_name}: {e}")
            await _emit("tool_result", {
                "tool": signal_type,
                "label": label,
                "results_count": 0,
                "signals_saved": 0,
                "error": str(e)[:200],
                "company_name": company_name,
            })

    # Hint-guided signal detection: budget signals
    for hint in hints.get("budget_signals", []):
        await _emit("tool_start", {
            "tool": "budget_signal",
            "label": f"Checking budget signal: {hint}...",
            "company_name": company_name,
        })
        try:
            detected = await _detect_hint_signal(company_name, domain, hint, "budget_signal")
            saved = await _save_signals(db, company_kb_id, "budget_signal", detected, company_name)
            await _emit("tool_result", {
                "tool": "budget_signal",
                "label": hint,
                "results_count": len(detected),
                "signals_saved": len(saved),
                "company_name": company_name,
            })
            for s in saved:
                await _emit("signal_found", {
                    "signal_type": s.signal_type,
                    "title": s.title[:200] if s.title else "",
                    "priority": s.priority,
                    "company_name": company_name,
                })
            new_signals.extend(saved)
        except Exception as e:
            logger.warning(f"Budget hint '{hint}' failed for {company_name}: {e}")

    # Hint-guided signal detection: urgency signals
    for hint in hints.get("urgency_signals", []):
        await _emit("tool_start", {
            "tool": "urgency_signal",
            "label": f"Checking urgency signal: {hint}...",
            "company_name": company_name,
        })
        try:
            detected = await _detect_hint_signal(company_name, domain, hint, "urgency_signal")
            saved = await _save_signals(db, company_kb_id, "urgency_signal", detected, company_name)
            await _emit("tool_result", {
                "tool": "urgency_signal",
                "label": hint,
                "results_count": len(detected),
                "signals_saved": len(saved),
                "company_name": company_name,
            })
            for s in saved:
                await _emit("signal_found", {
                    "signal_type": s.signal_type,
                    "title": s.title[:200] if s.title else "",
                    "priority": s.priority,
                    "company_name": company_name,
                })
            new_signals.extend(saved)
        except Exception as e:
            logger.warning(f"Urgency hint '{hint}' failed for {company_name}: {e}")

    # Hint-guided signal detection: custom hints
    for hint in hints.get("custom_hints", []):
        await _emit("tool_start", {
            "tool": "custom_signal",
            "label": f"Checking custom signal: {hint}...",
            "company_name": company_name,
        })
        try:
            detected = await _detect_hint_signal(company_name, domain, hint, "custom_signal")
            saved = await _save_signals(db, company_kb_id, "custom_signal", detected, company_name)
            await _emit("tool_result", {
                "tool": "custom_signal",
                "label": hint,
                "results_count": len(detected),
                "signals_saved": len(saved),
                "company_name": company_name,
            })
            for s in saved:
                await _emit("signal_found", {
                    "signal_type": s.signal_type,
                    "title": s.title[:200] if s.title else "",
                    "priority": s.priority,
                    "company_name": company_name,
                })
            new_signals.extend(saved)
        except Exception as e:
            logger.warning(f"Custom hint '{hint}' failed for {company_name}: {e}")

    if new_signals:
        await db.flush()

        # Run correlation engine on the company's signals
        try:
            from app.services.signal_correlation_engine import correlate_signals_for_company
            company_name = _clean_company_name(raw_name, domain)
            await correlate_signals_for_company(db, company_kb_id, company_name)
        except Exception as e:
            logger.warning(f"Signal correlation failed for {company_kb_id}: {e}")

    return new_signals


async def detect_signals_for_company_streaming(
    run_id: str,
    company_kb_id: UUID,
    user_id: UUID,
    signal_types: list[str] | None = None,
    signal_hints: dict | None = None,
) -> None:
    """Background task: detect signals with SSE progress events.

    Uses its own DB session (runs outside request lifecycle).
    Emits progress events via event_store so the frontend can show a progress bar.
    """
    from app.db.session import async_session
    from app.services import event_store

    async with async_session() as db:
        try:
            result = await db.execute(
                select(CompanyKnowledgeBase).where(CompanyKnowledgeBase.id == company_kb_id)
            )
            kb = result.scalar_one_or_none()
            if not kb:
                await event_store.push_event(run_id, {
                    "type": "signal_detection_failed",
                    "data": {"message": "Company not found"},
                })
                return

            raw_name = kb.canonical_name or kb.normalized_domain
            domain = kb.normalized_domain or ""
            company_name = _clean_company_name(raw_name, domain)
            types_to_check = signal_types or DEFAULT_SIGNAL_TYPES
            hints = signal_hints or {}

            # Build list of all steps: signal types + hint-guided checks
            steps: list[tuple[str, str | None]] = [(t, None) for t in types_to_check]
            for hint in hints.get("budget_signals", []):
                steps.append(("budget_signal", hint))
            for hint in hints.get("urgency_signals", []):
                steps.append(("urgency_signal", hint))
            for hint in hints.get("custom_hints", []):
                steps.append(("custom_signal", hint))

            total_steps = len(steps)
            new_signals: list[SignalEvent] = []

            for i, (signal_type, hint_text) in enumerate(steps):
                label = hint_text or signal_type.replace("_", " ").title()
                await event_store.push_event(run_id, {
                    "type": "signal_progress",
                    "data": {
                        "step": i,
                        "total": total_steps,
                        "signal_type": signal_type,
                        "label": f"Checking {label}...",
                        "percent": round((i / total_steps) * 100),
                        "signals_found": len(new_signals),
                    },
                })

                try:
                    if hint_text:
                        detected = await _detect_hint_signal(
                            company_name, domain, hint_text, signal_type,
                        )
                    else:
                        detected = await _detect_single_signal(
                            signal_type, company_name, domain, kb,
                        )
                    saved = await _save_signals(
                        db, company_kb_id, signal_type, detected, company_name,
                    )
                    new_signals.extend(saved)
                except Exception as e:
                    logger.warning(
                        f"Signal detection '{signal_type}' failed for {company_name}: {e}"
                    )

            if new_signals:
                await db.flush()

            # Recompute heat score
            heat = await recompute_signal_heat_for_company(db, company_kb_id)

            # Create notifications for high/critical signals
            from app.services.notification_service import create_notification
            for s in new_signals:
                if s.priority in ("high", "critical"):
                    await create_notification(
                        db,
                        user_id=user_id,
                        notification_type="signal_detected",
                        title=f"{s.signal_type}: {s.title[:200]}",
                        body=s.summary[:300] if s.summary else None,
                        signal_event_id=s.id,
                    )

            await db.commit()

            # Terminal event
            await event_store.push_event(run_id, {
                "type": "signal_detection_completed",
                "data": {
                    "signals_detected": len(new_signals),
                    "signal_heat_score": heat,
                    "signals": [
                        {
                            "id": str(s.id),
                            "signal_type": s.signal_type,
                            "priority": s.priority,
                            "title": s.title,
                        }
                        for s in new_signals
                    ],
                },
            })

        except Exception as e:
            logger.error(f"Streaming signal detection failed: {e}", exc_info=True)
            await event_store.push_event(run_id, {
                "type": "signal_detection_failed",
                "data": {"message": str(e)[:500]},
            })


async def _save_signals(
    db: AsyncSession,
    company_kb_id: UUID,
    signal_type: str,
    detected: list[dict],
    company_name: str,
) -> list[SignalEvent]:
    """Deduplicate and save detected signals. Returns new SignalEvent records."""
    saved = []
    for sig_data in detected:
        # Dedup: check for same type + similar subtype in last 7 days
        subtype = sig_data.get("subtype", "")
        existing = await db.execute(
            select(SignalEvent).where(
                SignalEvent.company_kb_id == company_kb_id,
                SignalEvent.signal_type == signal_type,
                SignalEvent.signal_subtype == subtype,
                SignalEvent.created_at >= datetime.now(timezone.utc) - timedelta(days=7),
                SignalEvent.is_archived == False,
            )
        )
        if existing.scalar_one_or_none():
            continue

        config = SIGNAL_CONFIG.get(signal_type, {})
        cold_days = config.get("cold_days", 30)

        title = sig_data.get("title", f"{signal_type} detected for {company_name}")
        source_url = sig_data.get("source_url") or ""

        # Extract evidence_date: when the real-world event actually occurred.
        # Try explicit field first, then parse from evidence/article metadata.
        evidence_date = _extract_evidence_date(sig_data)

        # Compute confidence score
        from app.services.confidence_scorer import score_inline
        confidence_label = score_inline(
            source_tool=sig_data.get("source_tool"),
            evidence=sig_data.get("evidence"),
            evidence_date=evidence_date,
        )

        signal = SignalEvent(
            company_kb_id=company_kb_id,
            signal_type=signal_type,
            signal_subtype=(sig_data.get("subtype") or "")[:100],
            signal_category=config.get("category", "event"),
            priority=sig_data.get("priority", "medium"),
            strength=sig_data.get("strength", 50.0),
            confidence=confidence_label,
            title=title[:490],
            summary=sig_data.get("summary"),
            evidence=sig_data.get("evidence"),
            source_tool=sig_data.get("source_tool"),
            source_url=source_url[:490] if source_url else None,
            source_class=sig_data.get("source_class"),
            detected_at=datetime.now(timezone.utc),
            evidence_date=evidence_date,
            expires_at=datetime.now(timezone.utc) + timedelta(days=cold_days),
        )
        db.add(signal)
        saved.append(signal)
    return saved


def _extract_evidence_date(sig_data: dict) -> datetime | None:
    """Extract the real-world event date from signal data.

    Checks multiple sources in order:
    1. Explicit evidence_date field (from agent-based detection)
    2. Published date from article metadata in evidence
    3. Returns None if no date found (will display as "unknown freshness")
    """
    # 1. Explicit evidence_date from agent output
    date_str = sig_data.get("evidence_date")
    if date_str:
        parsed = _try_parse_date(date_str)
        if parsed:
            return parsed

    # 2. Look inside evidence dict for article dates
    evidence = sig_data.get("evidence") or {}
    articles = evidence.get("articles", [])
    for article in articles:
        for key in ("published_date", "pub_date", "dateTime", "date", "publishedAt"):
            val = article.get(key)
            if val:
                parsed = _try_parse_date(val)
                if parsed:
                    return parsed

    # 3. Recency_months from agent output (approximate)
    recency = sig_data.get("recency_months")
    if recency is not None:
        try:
            months = float(recency)
            return datetime.now(timezone.utc) - timedelta(days=int(months * 30))
        except (ValueError, TypeError):
            pass

    return None


def _try_parse_date(value: str | datetime) -> datetime | None:
    """Try to parse various date formats into a timezone-aware datetime."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    if not isinstance(value, str) or not value.strip():
        return None

    value = value.strip()
    import re

    # Common formats
    formats = [
        "%Y-%m-%d",           # 2026-04-15
        "%Y-%m-%dT%H:%M:%S",  # 2026-04-15T10:30:00
        "%Y-%m-%dT%H:%M:%SZ", # 2026-04-15T10:30:00Z
        "%B %d, %Y",          # April 15, 2026
        "%b %d, %Y",          # Apr 15, 2026
        "%d %B %Y",           # 15 April 2026
        "%d %b %Y",           # 15 Apr 2026
        "%m/%d/%Y",           # 04/15/2026
        "%Y/%m/%d",           # 2026/04/15
    ]

    # Strip timezone suffix for parsing
    clean = re.sub(r'[+-]\d{2}:?\d{2}$', '', value)
    clean = clean.rstrip('Z')

    for fmt in formats:
        try:
            dt = datetime.strptime(clean, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


async def _detect_single_signal(
    signal_type: str,
    company_name: str,
    domain: str,
    kb: CompanyKnowledgeBase,
) -> list[dict]:
    """Run tool(s) for a specific signal type and extract findings.

    Returns a list of signal data dicts, or empty list if nothing found.
    """
    results = []

    if signal_type == "funding":
        results = await _detect_funding(company_name)
    elif signal_type == "hiring_surge":
        results = await _detect_hiring(company_name, domain)
    elif signal_type == "executive_change":
        results = await _detect_executive_change(company_name, domain, kb)
    elif signal_type == "product_launch":
        results = await _detect_product_launch(company_name)
    elif signal_type == "press_mention":
        results = await _detect_press(company_name)
    elif signal_type == "partnership":
        results = await _detect_partnership(company_name)
    elif signal_type == "earnings_report":
        results = await _detect_earnings(company_name, kb)
    elif signal_type == "expansion":
        results = await _detect_expansion(company_name)
    elif signal_type == "tech_adoption":
        results = await _detect_tech_adoption(domain, kb)

    return results


# ── Hint-guided signal detection ──

def _clean_company_name(name: str, domain: str) -> str:
    """Extract a clean company name from canonical_name or domain.

    E.g., "snowflake.com" → "Snowflake", "HubSpot" → "HubSpot"
    """
    # If the name looks like a domain, extract the company part
    if "." in name and not " " in name:
        base = name.split(".")[0]
        return base.capitalize() if base == base.lower() else base
    return name


async def _detect_hint_signal(
    company_name: str,
    domain: str,
    hint: str,
    signal_type: str,
) -> list[dict]:
    """Detect a signal guided by a user-provided hint.

    Uses multiple search strategies to find evidence of the hint for this company.
    E.g., hint="cloud migration budget" → search for evidence that company
    is investing in cloud migration.
    """
    results = []
    hint_lower = hint.lower().strip()
    if not hint_lower:
        return []

    # Use clean company name for search (not "snowflake.com" but "Snowflake")
    clean_name = _clean_company_name(company_name, domain)
    company_terms = {clean_name.lower(), company_name.lower()}
    # Also match base domain (e.g., "snowflake" from "snowflake.com")
    if domain:
        company_terms.add(domain.split(".")[0].lower())

    # Strategy 1: Multi-source news search with hint terms
    try:
        search_query = f'"{clean_name}" {hint}'
        articles, source_tool = await resilient_search(
            query=search_query,
            max_results=5,
            company_name=clean_name,
        )
        # Filter for relevance: article must mention the company
        relevant = []
        for article in articles:
            title = (article.get("title") or "").lower()
            body = (article.get("body") or article.get("content") or "").lower()
            text = f"{title} {body}"
            # Must mention company name or domain base
            if any(term in text for term in company_terms):
                # Must mention at least part of the hint
                hint_words = [w for w in hint_lower.split() if len(w) > 3]
                if any(w in text for w in hint_words) or hint_lower in text:
                    relevant.append(article)

        if relevant:
            best = relevant[0]
            title = best.get("title", "") or ""
            body = best.get("body", "") or best.get("content", "") or ""

            # Determine priority based on how strongly the evidence matches
            match_count = sum(1 for w in hint_lower.split() if w in f"{title} {body}".lower())
            if match_count >= 3:
                priority = "high"
                strength = 75.0
            elif match_count >= 2:
                priority = "medium"
                strength = 60.0
            else:
                priority = "medium"
                strength = 50.0

            type_label = {
                "budget_signal": "Budget",
                "urgency_signal": "Urgency",
                "custom_signal": "Custom",
            }.get(signal_type, "Signal")

            results.append({
                "subtype": hint_lower.replace(" ", "_")[:100],
                "priority": priority,
                "strength": strength,
                "title": f"{type_label}: {hint} — {title[:150]}",
                "summary": body[:500] if body else None,
                "evidence": {
                    "hint": hint,
                    "signal_type": signal_type,
                    "articles": relevant[:3],
                },
                "source_tool": source_tool,
                "source_url": best.get("href") or best.get("url"),
            })
    except Exception as e:
        logger.warning(f"Hint detection error for '{hint}': {e}")

    # Strategy 2: For budget signals, also try financial-focused search
    if signal_type == "budget_signal" and not results:
        try:
            articles, source_tool = await resilient_search(
                query=f'"{clean_name}" budget OR investment OR spending OR allocating "{hint}"',
                max_results=5,
                company_name=clean_name,
            )
            for article in articles:
                title = (article.get("title") or "").lower()
                body = (article.get("body") or article.get("content") or "").lower()
                text = f"{title} {body}"
                if any(term in text for term in company_terms):
                    results.append({
                        "subtype": hint_lower.replace(" ", "_")[:100],
                        "priority": "medium",
                        "strength": 55.0,
                        "title": f"Budget: {hint} — {(article.get('title') or '')[:150]}",
                        "summary": (article.get("body") or "")[:500],
                        "evidence": {"hint": hint, "articles": articles[:3]},
                        "source_tool": source_tool,
                        "source_url": article.get("href") or article.get("url"),
                    })
                    break
        except Exception as e:
            logger.warning(f"Budget hint fallback error for {clean_name}: {e}")

    # Strategy 3: For urgency signals, search for time-sensitive language
    if signal_type == "urgency_signal" and not results:
        try:
            articles, source_tool = await resilient_search(
                query=f'"{clean_name}" deadline OR "urgently" OR "immediate" OR "timeline" "{hint}"',
                max_results=5,
                company_name=clean_name,
            )
            for article in articles:
                title = (article.get("title") or "").lower()
                body = (article.get("body") or article.get("content") or "").lower()
                text = f"{title} {body}"
                if any(term in text for term in company_terms):
                    results.append({
                        "subtype": hint_lower.replace(" ", "_")[:100],
                        "priority": "high",
                        "strength": 65.0,
                        "title": f"Urgency: {hint} — {(article.get('title') or '')[:150]}",
                        "summary": (article.get("body") or "")[:500],
                        "evidence": {"hint": hint, "articles": articles[:3]},
                        "source_tool": source_tool,
                        "source_url": article.get("href") or article.get("url"),
                    })
                    break
        except Exception as e:
            logger.warning(f"Urgency hint fallback error for {clean_name}: {e}")

    return results


# ── Individual signal detectors ──

async def _detect_funding(company_name: str) -> list[dict]:
    """Detect funding signals via news search."""
    try:
        articles, source_tool = await resilient_search(
            query=f'"{company_name}" funding OR "series" OR "raised" OR "investment"',
            max_results=5,
            company_name=company_name,
        )
        for article in articles:
            title = (article.get("title") or "").lower()
            body = (article.get("body") or article.get("content") or "").lower()
            text = f"{title} {body}"
            if any(kw in text for kw in ["funding", "raised", "series", "investment", "venture", "round"]):
                amount_hint = _extract_amount(text)
                priority = "high" if amount_hint and amount_hint >= 10_000_000 else "medium"
                return [{
                    "subtype": "funding_round",
                    "priority": priority,
                    "strength": 80.0 if priority == "high" else 60.0,
                    "title": (article.get("title") or "")[:200] or f"Funding signal for {company_name}",
                    "summary": (article.get("body") or article.get("content") or "")[:500] or None,
                    "evidence": {"articles": articles[:3]},
                    "source_tool": source_tool,
                    "source_url": article.get("href") or article.get("url"),
                }]
    except Exception as e:
        logger.warning(f"Funding detection error for {company_name}: {e}")
    return []


async def _detect_hiring(company_name: str, domain: str) -> list[dict]:
    """Detect hiring surge via job posting search."""
    try:
        articles, source_tool = await resilient_search(
            query=f'"{company_name}" hiring OR "open positions" OR "we are hiring" OR careers',
            max_results=5,
            company_name=company_name,
        )
        hiring_signals = [a for a in articles if any(
            kw in ((a.get("title") or "") + (a.get("body") or "")).lower()
            for kw in ["hiring", "open position", "job opening", "careers", "join our team"]
        )]
        if len(hiring_signals) >= 2:
            return [{
                "subtype": "multiple_openings",
                "priority": "medium",
                "strength": 55.0,
                "title": f"{company_name} appears to be actively hiring",
                "summary": f"Found {len(hiring_signals)} hiring-related results",
                "evidence": {"articles": hiring_signals[:3]},
                "source_tool": source_tool,
            }]
    except Exception as e:
        logger.warning(f"Hiring detection error for {company_name}: {e}")
    return []


async def _detect_executive_change(
    company_name: str, domain: str, kb: CompanyKnowledgeBase,
) -> list[dict]:
    """Detect executive changes via news search."""
    try:
        articles, source_tool = await resilient_search(
            query=f'"{company_name}" "new CEO" OR "new CTO" OR "appointed" OR "named" OR "joins as"',
            max_results=5,
            company_name=company_name,
        )
        for article in articles:
            title = (article.get("title") or "")
            body = (article.get("body") or article.get("content") or "")
            text = f"{title} {body}".lower()
            if any(kw in text for kw in ["appointed", "named", "joins as", "new ceo", "new cto", "new vp"]):
                is_c_suite = any(t in text for t in ["ceo", "cto", "cfo", "coo", "cro", "chief"])
                return [{
                    "subtype": "c_suite_change" if is_c_suite else "vp_change",
                    "priority": "high" if is_c_suite else "medium",
                    "strength": 75.0 if is_c_suite else 55.0,
                    "title": title[:200] or f"Executive change at {company_name}",
                    "summary": body[:500] if body else None,
                    "evidence": {"articles": articles[:3]},
                    "source_tool": source_tool,
                    "source_url": article.get("href") or article.get("url"),
                }]
    except Exception as e:
        logger.warning(f"Executive change detection error for {company_name}: {e}")
    return []


async def _detect_product_launch(company_name: str) -> list[dict]:
    """Detect product launches via news."""
    try:
        articles, source_tool = await resilient_search(
            query=f'"{company_name}" "launches" OR "announces" OR "new product" OR "new feature"',
            max_results=5,
            company_name=company_name,
        )
        for article in articles:
            title = (article.get("title") or "")
            body = (article.get("body") or article.get("content") or "")
            text = f"{title} {body}".lower()
            if any(kw in text for kw in ["launch", "announc", "new product", "new feature", "release"]):
                return [{
                    "subtype": "product_announcement",
                    "priority": "medium",
                    "strength": 55.0,
                    "title": title[:200] or f"Product announcement from {company_name}",
                    "summary": body[:500] if body else None,
                    "evidence": {"articles": articles[:3]},
                    "source_tool": source_tool,
                    "source_url": article.get("href") or article.get("url"),
                }]
    except Exception as e:
        logger.warning(f"Product launch detection error for {company_name}: {e}")
    return []


async def _detect_press(company_name: str) -> list[dict]:
    """Detect significant press mentions."""
    try:
        articles, source_tool = await resilient_search(
            query=f'"{company_name}"',
            max_results=5,
            company_name=company_name,
        )
        # Verify at least one article actually mentions the company
        name_lower = company_name.lower()
        relevant = [
            a for a in articles
            if name_lower in ((a.get("title") or "") + (a.get("body") or "")).lower()
        ]
        if len(relevant) >= 3:
            return [{
                "subtype": "media_coverage",
                "priority": "low",
                "strength": 35.0,
                "title": f"Recent press mentions for {company_name}",
                "summary": f"Found {len(relevant)} recent mentions",
                "evidence": {"articles": relevant[:5]},
                "source_tool": source_tool,
            }]
    except Exception as e:
        logger.warning(f"Press detection error for {company_name}: {e}")
    return []


async def _detect_partnership(company_name: str) -> list[dict]:
    """Detect partnership announcements."""
    try:
        articles, source_tool = await resilient_search(
            query=f'"{company_name}" "partnership" OR "partners with" OR "strategic alliance" OR "collaboration"',
            max_results=5,
            company_name=company_name,
        )
        for article in articles:
            title = (article.get("title") or "")
            body = (article.get("body") or article.get("content") or "")
            text = f"{title} {body}".lower()
            if any(kw in text for kw in ["partner", "alliance", "collaborat", "joint venture"]):
                return [{
                    "subtype": "partnership_announcement",
                    "priority": "medium",
                    "strength": 55.0,
                    "title": title[:200] or f"Partnership signal for {company_name}",
                    "summary": body[:500] if body else None,
                    "evidence": {"articles": articles[:3]},
                    "source_tool": source_tool,
                    "source_url": article.get("href") or article.get("url"),
                }]
    except Exception as e:
        logger.warning(f"Partnership detection error for {company_name}: {e}")
    return []


async def _detect_earnings(company_name: str, kb: CompanyKnowledgeBase) -> list[dict]:
    """Detect earnings reports / financial events."""
    try:
        articles, source_tool = await resilient_search(
            query=f'"{company_name}" "earnings" OR "quarterly results" OR "financial results" OR "revenue"',
            max_results=5,
            company_name=company_name,
        )
        for article in articles:
            title = (article.get("title") or "")
            text = title.lower()
            if any(kw in text for kw in ["earnings", "quarterly", "financial results", "revenue growth"]):
                return [{
                    "subtype": "earnings_release",
                    "priority": "medium",
                    "strength": 50.0,
                    "title": title[:200] or f"Financial update for {company_name}",
                    "evidence": {"articles": articles[:3]},
                    "source_tool": source_tool,
                    "source_url": article.get("href") or article.get("url"),
                }]
    except Exception as e:
        logger.warning(f"Earnings detection error for {company_name}: {e}")
    return []


async def _detect_expansion(company_name: str) -> list[dict]:
    """Detect expansion signals (new offices, markets)."""
    try:
        articles, source_tool = await resilient_search(
            query=f'"{company_name}" "new office" OR "expands to" OR "expansion" OR "opens" OR "enters market"',
            max_results=5,
            company_name=company_name,
        )
        for article in articles:
            title = (article.get("title") or "")
            body = (article.get("body") or article.get("content") or "")
            text = f"{title} {body}".lower()
            if any(kw in text for kw in ["new office", "expand", "opens", "enters market", "headquart"]):
                return [{
                    "subtype": "geographic_expansion",
                    "priority": "medium",
                    "strength": 50.0,
                    "title": title[:200] or f"Expansion signal for {company_name}",
                    "summary": body[:500] if body else None,
                    "evidence": {"articles": articles[:3]},
                    "source_tool": source_tool,
                    "source_url": article.get("href") or article.get("url"),
                }]
    except Exception as e:
        logger.warning(f"Expansion detection error for {company_name}: {e}")
    return []


async def _detect_tech_adoption(domain: str, kb: CompanyKnowledgeBase) -> list[dict]:
    """Detect technology adoption changes via web scraping."""
    if not domain:
        return []
    try:
        from app.tools.web_scraper_tool import scrape_webpage
        raw = await asyncio.to_thread(
            scrape_webpage,
            url=f"https://{domain}",
        )
        tech_signals = raw.get("tech_signals", []) if isinstance(raw, dict) else []
        if tech_signals:
            old_tech = kb.tech_stack_json or []
            new_tech = [t for t in tech_signals if t not in old_tech]
            if new_tech:
                return [{
                    "subtype": "new_technology",
                    "priority": "low",
                    "strength": 40.0,
                    "title": f"{kb.canonical_name} adopted new technologies: {', '.join(new_tech[:5])}",
                    "evidence": {"new_tech": new_tech, "all_tech": tech_signals},
                    "source_tool": "web_scraper",
                }]
    except Exception as e:
        logger.warning(f"Tech adoption detection error for {domain}: {e}")
    return []


def _extract_amount(text: str) -> int | None:
    """Extract dollar amount from text (e.g., '$50M', '$200 million')."""
    import re
    patterns = [
        (r"\$(\d+(?:\.\d+)?)\s*(?:billion|b)\b", 1_000_000_000),
        (r"\$(\d+(?:\.\d+)?)\s*(?:million|m)\b", 1_000_000),
        (r"\$(\d+(?:\.\d+)?)\s*(?:thousand|k)\b", 1_000),
    ]
    for pattern, multiplier in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(float(match.group(1)) * multiplier)
    return None


# ──────────────────────────────────────────────────────────────────
# Signal Heat computation (composite score with decay)
# ──────────────────────────────────────────────────────────────────

def compute_signal_heat(signals: list[SignalEvent]) -> float:
    """Compute composite signal heat score for a set of active signals.

    Formula: sum(weight * decay(age) * strength/100) normalized to 0-100.
    """
    if not signals:
        return 0.0

    now = datetime.now(timezone.utc)
    total = 0.0

    for signal in signals:
        if signal.is_archived or signal.is_dismissed:
            continue

        config = SIGNAL_CONFIG.get(signal.signal_type, {})
        weight = config.get("default_weight", 1.0)
        half_life = config.get("half_life_days", 7)

        # Compute age in days from evidence_date (actual event age, not discovery age)
        event_date = signal.evidence_date or signal.detected_at or signal.created_at
        if event_date and event_date.tzinfo is None:
            event_date = event_date.replace(tzinfo=timezone.utc)
        age_days = (now - event_date).total_seconds() / 86400 if event_date else 0

        # Exponential decay: 0.5^(age/half_life)
        decay = math.pow(0.5, age_days / half_life) if half_life > 0 else 1.0

        strength = (signal.strength or 50.0) / 100.0
        total += weight * decay * strength

    # Normalize: cap at 100, with diminishing returns via log scaling
    # 1 strong fresh signal ≈ 50-60, 3 signals ≈ 80, 5+ ≈ 90+
    if total <= 0:
        return 0.0

    normalized = 100.0 * (1.0 - math.exp(-total * 0.7))
    return round(min(normalized, 100.0), 1)


async def recompute_signal_heat_for_company(
    db: AsyncSession,
    company_kb_id: UUID,
) -> float:
    """Recompute and materialize signal heat for all tracking list memberships
    that include this company.
    """
    # Get active signals
    result = await db.execute(
        select(SignalEvent).where(
            SignalEvent.company_kb_id == company_kb_id,
            SignalEvent.is_archived == False,
            SignalEvent.is_dismissed == False,
        )
    )
    signals = list(result.scalars().all())
    heat = compute_signal_heat(signals)

    # Update all memberships for this company
    await db.execute(
        update(TrackingListMembership)
        .where(TrackingListMembership.company_kb_id == company_kb_id)
        .values(signal_heat_score=heat)
    )
    await db.flush()

    return heat


# ──────────────────────────────────────────────────────────────────
# Signal feed / history queries
# ──────────────────────────────────────────────────────────────────

async def get_signals_for_company(
    db: AsyncSession,
    company_kb_id: UUID,
    limit: int = 50,
    include_archived: bool = False,
) -> list[SignalEvent]:
    """Get signal history for a company, sorted by evidence freshness (newest real-world events first)."""
    from sqlalchemy import func as sa_func
    query = (
        select(SignalEvent)
        .where(SignalEvent.company_kb_id == company_kb_id)
    )
    if not include_archived:
        query = query.where(
            SignalEvent.is_archived == False,
            SignalEvent.is_dismissed == False,
        )
    # Sort by evidence_date (actual event time), falling back to detected_at
    query = query.order_by(
        sa_func.coalesce(SignalEvent.evidence_date, SignalEvent.detected_at).desc()
    ).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


async def _get_user_tracked_kb_ids(db: AsyncSession, user_id: UUID) -> list[UUID]:
    """Get all company KB IDs from user's active tracking lists."""
    from app.models.tracking_list import TrackingList
    list_result = await db.execute(
        select(TrackingList.id).where(
            TrackingList.user_id == user_id,
            TrackingList.is_active == True,
        )
    )
    list_ids = [row[0] for row in list_result.all()]
    if not list_ids:
        return []
    membership_result = await db.execute(
        select(TrackingListMembership.company_kb_id).where(
            TrackingListMembership.tracking_list_id.in_(list_ids)
        ).distinct()
    )
    return [row[0] for row in membership_result.all()]


async def get_signal_feed(
    db: AsyncSession,
    user_id: UUID,
    signal_type: str | None = None,
    priority: str | None = None,
    tab: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int, int]:
    """Get unified signal feed across all of a user's tracking lists.

    Args:
        tab: Feed tab filter — "all" (default), "today", "week", "saved"

    Returns:
        (feed_items, total_count, snoozed_returned_count)
    """
    kb_ids = await _get_user_tracked_kb_ids(db, user_id)
    if not kb_ids:
        return [], 0, 0

    # First, unsnooze any returned signals
    returned = await unsnooze_returned_signals(db)
    snoozed_returned = await get_snoozed_returned_count(db, kb_ids) + returned

    # Base filters
    from sqlalchemy import func
    base_filters = [
        SignalEvent.company_kb_id.in_(kb_ids),
        SignalEvent.is_archived == False,
        SignalEvent.is_dismissed == False,
        SignalEvent.is_snoozed == False,
    ]

    # Tab-specific filters
    now = datetime.now(timezone.utc)
    if tab == "today":
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        base_filters.append(
            func.coalesce(SignalEvent.evidence_date, SignalEvent.detected_at) >= start_of_day
        )
    elif tab == "week":
        start_of_week = now - timedelta(days=7)
        base_filters.append(
            func.coalesce(SignalEvent.evidence_date, SignalEvent.detected_at) >= start_of_week
        )
    elif tab == "saved":
        base_filters.append(SignalEvent.is_saved == True)

    count_query = select(func.count(SignalEvent.id)).where(*base_filters)
    query = (
        select(SignalEvent, CompanyKnowledgeBase.canonical_name, CompanyKnowledgeBase.normalized_domain)
        .join(CompanyKnowledgeBase, SignalEvent.company_kb_id == CompanyKnowledgeBase.id)
        .where(*base_filters)
    )

    if signal_type:
        query = query.where(SignalEvent.signal_type == signal_type)
        count_query = count_query.where(SignalEvent.signal_type == signal_type)
    if priority:
        query = query.where(SignalEvent.priority == priority)
        count_query = count_query.where(SignalEvent.priority == priority)

    total = (await db.execute(count_query)).scalar() or 0

    from sqlalchemy import func as sa_func
    query = query.order_by(
        sa_func.coalesce(SignalEvent.evidence_date, SignalEvent.detected_at).desc()
    ).offset(offset).limit(limit)
    result = await db.execute(query)
    rows = result.all()

    feed = []
    for signal, company_name, domain in rows:
        feed.append({
            "id": str(signal.id),
            "company_kb_id": str(signal.company_kb_id),
            "company_name": company_name,
            "domain": domain,
            "signal_type": signal.signal_type,
            "signal_subtype": signal.signal_subtype,
            "signal_category": signal.signal_category,
            "priority": signal.priority,
            "strength": signal.strength,
            "title": signal.title,
            "summary": signal.summary,
            "source_url": signal.source_url,
            "source_tool": signal.source_tool,
            "is_saved": signal.is_saved,
            "detected_at": signal.detected_at.isoformat() if signal.detected_at else None,
            "evidence_date": signal.evidence_date.isoformat() if signal.evidence_date else None,
            "created_at": signal.created_at.isoformat() if signal.created_at else None,
        })

    return feed, total, snoozed_returned


async def get_dashboard_signal_stats(
    db: AsyncSession,
    user_id: UUID,
) -> dict:
    """Get signal stats for dashboard display.

    Results are cached for 60 seconds per user to reduce dashboard load queries.
    """
    from app.services.cache_service import cache_get, cache_set
    cache_key = f"dashboard_stats:{user_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    # (original implementation follows — result cached at the end)
    kb_ids = await _get_user_tracked_kb_ids(db, user_id)
    if not kb_ids:
        return {
            "total_active": 0,
            "this_week": 0,
            "saved_count": 0,
            "snoozed_count": 0,
            "top_signals": [],
            "by_type": {},
        }

    from sqlalchemy import func
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    active_filters = [
        SignalEvent.company_kb_id.in_(kb_ids),
        SignalEvent.is_archived == False,
        SignalEvent.is_dismissed == False,
    ]

    # Total active
    total_active = (await db.execute(
        select(func.count(SignalEvent.id)).where(*active_filters, SignalEvent.is_snoozed == False)
    )).scalar() or 0

    # This week
    this_week = (await db.execute(
        select(func.count(SignalEvent.id)).where(
            *active_filters,
            func.coalesce(SignalEvent.evidence_date, SignalEvent.detected_at) >= week_ago,
        )
    )).scalar() or 0

    # Saved count
    saved_count = (await db.execute(
        select(func.count(SignalEvent.id)).where(*active_filters, SignalEvent.is_saved == True)
    )).scalar() or 0

    # Snoozed count
    snoozed_count = (await db.execute(
        select(func.count(SignalEvent.id)).where(
            SignalEvent.company_kb_id.in_(kb_ids),
            SignalEvent.is_snoozed == True,
        )
    )).scalar() or 0

    # Top 3 recent high-priority signals
    from sqlalchemy import func as sa_func
    top_result = await db.execute(
        select(SignalEvent, CompanyKnowledgeBase.canonical_name, CompanyKnowledgeBase.normalized_domain)
        .join(CompanyKnowledgeBase, SignalEvent.company_kb_id == CompanyKnowledgeBase.id)
        .where(
            *active_filters,
            SignalEvent.is_snoozed == False,
            SignalEvent.priority.in_(["critical", "high"]),
        )
        .order_by(sa_func.coalesce(SignalEvent.evidence_date, SignalEvent.detected_at).desc())
        .limit(3)
    )
    top_signals = []
    for signal, company_name, domain in top_result.all():
        top_signals.append({
            "id": str(signal.id),
            "company_kb_id": str(signal.company_kb_id),
            "company_name": company_name,
            "domain": domain,
            "signal_type": signal.signal_type,
            "priority": signal.priority,
            "title": signal.title,
            "summary": signal.summary,
            "source_url": signal.source_url,
            "detected_at": signal.detected_at.isoformat() if signal.detected_at else None,
            "evidence_date": signal.evidence_date.isoformat() if signal.evidence_date else None,
        })

    # Breakdown by type
    type_result = await db.execute(
        select(SignalEvent.signal_type, func.count(SignalEvent.id))
        .where(*active_filters, SignalEvent.is_snoozed == False)
        .group_by(SignalEvent.signal_type)
    )
    by_type = {row[0]: row[1] for row in type_result.all()}

    # Correlation count (recent activity events of type correlation_found)
    from app.models.activity_event import ActivityEvent
    correlation_count = (await db.execute(
        select(func.count(ActivityEvent.id)).where(
            ActivityEvent.company_kb_id.in_(kb_ids),
            ActivityEvent.event_type == "correlation_found",
            ActivityEvent.created_at >= week_ago,
        )
    )).scalar() or 0

    # Custom rules count
    from app.models.custom_signal_rule import CustomSignalRule
    rules_count = (await db.execute(
        select(func.count(CustomSignalRule.id)).where(
            CustomSignalRule.user_id == user_id,
            CustomSignalRule.is_active == True,
        )
    )).scalar() or 0

    return {
        "total_active": total_active,
        "this_week": this_week,
        "saved_count": saved_count,
        "snoozed_count": snoozed_count,
        "top_signals": top_signals,
        "by_type": by_type,
        "correlations_this_week": correlation_count,
        "active_rules_count": rules_count,
    }

    cache_set(cache_key, result, ttl=60)
    return result


# ──────────────────────────────────────────────────────────────────
# Signal lifecycle management
# ──────────────────────────────────────────────────────────────────

async def dismiss_signal(db: AsyncSession, signal_id: UUID) -> bool:
    result = await db.execute(
        select(SignalEvent).where(SignalEvent.id == signal_id)
    )
    signal = result.scalar_one_or_none()
    if not signal:
        return False
    signal.is_dismissed = True
    await db.flush()
    return True


async def save_signal(db: AsyncSession, signal_id: UUID) -> bool:
    """Bookmark/save a signal for later reference."""
    result = await db.execute(
        select(SignalEvent).where(SignalEvent.id == signal_id)
    )
    signal = result.scalar_one_or_none()
    if not signal:
        return False
    signal.is_saved = True
    signal.saved_at = datetime.now(timezone.utc)
    await db.flush()
    return True


async def unsave_signal(db: AsyncSession, signal_id: UUID) -> bool:
    """Remove save/bookmark from a signal."""
    result = await db.execute(
        select(SignalEvent).where(SignalEvent.id == signal_id)
    )
    signal = result.scalar_one_or_none()
    if not signal:
        return False
    signal.is_saved = False
    signal.saved_at = None
    await db.flush()
    return True


async def snooze_signal(db: AsyncSession, signal_id: UUID, duration_hours: int) -> bool:
    """Snooze a signal for a given number of hours. It will reappear after the duration."""
    result = await db.execute(
        select(SignalEvent).where(SignalEvent.id == signal_id)
    )
    signal = result.scalar_one_or_none()
    if not signal:
        return False
    now = datetime.now(timezone.utc)
    signal.is_snoozed = True
    signal.snoozed_at = now
    signal.snoozed_until = now + timedelta(hours=duration_hours)
    await db.flush()
    return True


async def unsnooze_returned_signals(db: AsyncSession) -> int:
    """Unsnooze signals whose snooze period has expired. Returns count of returned signals."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        update(SignalEvent)
        .where(
            SignalEvent.is_snoozed == True,
            SignalEvent.snoozed_until <= now,
        )
        .values(is_snoozed=False, snoozed_until=None, snoozed_at=None)
    )
    await db.flush()
    return result.rowcount


async def get_snoozed_returned_count(db: AsyncSession, kb_ids: list[UUID]) -> int:
    """Count signals that just returned from snooze (unsnooze happened within last 24h).

    These are signals where is_snoozed=False but snoozed_at is recent,
    indicating they recently came back. Since unsnooze clears snoozed_at,
    we instead count signals that were snoozed but snoozed_until has passed.
    """
    if not kb_ids:
        return 0
    from sqlalchemy import func
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(hours=24)
    result = await db.execute(
        select(func.count(SignalEvent.id)).where(
            SignalEvent.company_kb_id.in_(kb_ids),
            SignalEvent.is_snoozed == True,
            SignalEvent.snoozed_until <= now,
            SignalEvent.snoozed_until >= yesterday,
        )
    )
    return result.scalar() or 0


async def archive_expired_signals(db: AsyncSession) -> int:
    """Archive signals past their expiration date."""
    result = await db.execute(
        update(SignalEvent)
        .where(
            SignalEvent.expires_at <= datetime.now(timezone.utc),
            SignalEvent.is_archived == False,
        )
        .values(is_archived=True)
    )
    await db.flush()
    return result.rowcount
