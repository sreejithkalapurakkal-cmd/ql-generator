"""Custom Signal Rules service.

CRUD operations for user-defined signal detection rules.
Evaluation of keyword and composite rules against signal data.
"""
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.custom_signal_rule import CustomSignalRule
from app.models.signal_event import SignalEvent

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# CRUD
# ──────────────────────────────────────────────────────────────────

async def create_rule(
    db: AsyncSession,
    user_id: UUID,
    name: str,
    rule_type: str,
    rule_config: dict,
    description: str | None = None,
    tracking_list_id: UUID | None = None,
    signal_type_output: str = "custom_signal",
    priority_output: str = "medium",
) -> CustomSignalRule:
    rule = CustomSignalRule(
        user_id=user_id,
        tracking_list_id=tracking_list_id,
        name=name,
        description=description,
        rule_type=rule_type,
        rule_config=rule_config,
        signal_type_output=signal_type_output,
        priority_output=priority_output,
    )
    db.add(rule)
    await db.flush()
    return rule


async def get_rules_for_user(
    db: AsyncSession,
    user_id: UUID,
    tracking_list_id: UUID | None = None,
    active_only: bool = False,
) -> list[CustomSignalRule]:
    query = select(CustomSignalRule).where(CustomSignalRule.user_id == user_id)
    if tracking_list_id:
        query = query.where(
            (CustomSignalRule.tracking_list_id == tracking_list_id)
            | (CustomSignalRule.tracking_list_id.is_(None))
        )
    if active_only:
        query = query.where(CustomSignalRule.is_active == True)
    query = query.order_by(CustomSignalRule.created_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_rule(db: AsyncSession, rule_id: UUID) -> CustomSignalRule | None:
    result = await db.execute(
        select(CustomSignalRule).where(CustomSignalRule.id == rule_id)
    )
    return result.scalar_one_or_none()


async def update_rule(
    db: AsyncSession,
    rule_id: UUID,
    **kwargs,
) -> CustomSignalRule | None:
    rule = await get_rule(db, rule_id)
    if not rule:
        return None
    for key, value in kwargs.items():
        if hasattr(rule, key) and value is not None:
            setattr(rule, key, value)
    await db.flush()
    return rule


async def delete_rule(db: AsyncSession, rule_id: UUID) -> bool:
    rule = await get_rule(db, rule_id)
    if not rule:
        return False
    await db.delete(rule)
    await db.flush()
    return True


async def toggle_rule(db: AsyncSession, rule_id: UUID) -> CustomSignalRule | None:
    rule = await get_rule(db, rule_id)
    if not rule:
        return None
    rule.is_active = not rule.is_active
    await db.flush()
    return rule


# ──────────────────────────────────────────────────────────────────
# Rule Evaluation
# ──────────────────────────────────────────────────────────────────

def evaluate_keyword_rule(rule: CustomSignalRule, text: str) -> bool:
    """Evaluate a keyword rule against text.

    rule_config: {keywords: ["cloud", "migration"], match_any: true}
    """
    config = rule.rule_config or {}
    keywords = config.get("keywords", [])
    match_any = config.get("match_any", True)

    if not keywords:
        return False

    text_lower = text.lower()
    matches = [kw.lower() in text_lower for kw in keywords]

    return any(matches) if match_any else all(matches)


def evaluate_pattern_rule(rule: CustomSignalRule, text: str) -> bool:
    """Evaluate a regex pattern rule against text.

    rule_config: {pattern: "raised?.*\\$\\d+[MBmb]", field: "title"}
    """
    config = rule.rule_config or {}
    pattern = config.get("pattern", "")

    if not pattern:
        return False

    try:
        return bool(re.search(pattern, text, re.IGNORECASE))
    except re.error:
        logger.warning(f"Invalid regex pattern in rule {rule.id}: {pattern}")
        return False


async def evaluate_composite_rule(
    db: AsyncSession,
    rule: CustomSignalRule,
    company_kb_id: UUID,
) -> bool:
    """Evaluate a composite rule against existing signals for a company.

    rule_config: {
        conditions: [
            {signal_type: "funding", min_count: 1, within_days: 90},
            {signal_type: "hiring_surge", min_count: 1, within_days: 90}
        ],
        operator: "all"  # all conditions must match
    }
    """
    config = rule.rule_config or {}
    conditions = config.get("conditions", [])
    operator = config.get("operator", "all")

    if not conditions:
        return False

    from sqlalchemy import func
    now = datetime.now(timezone.utc)
    results = []

    for condition in conditions:
        signal_type = condition.get("signal_type")
        min_count = condition.get("min_count", 1)
        within_days = condition.get("within_days", 90)

        if not signal_type:
            results.append(False)
            continue

        from datetime import timedelta
        cutoff = now - timedelta(days=within_days)

        count_result = await db.execute(
            select(func.count(SignalEvent.id)).where(
                SignalEvent.company_kb_id == company_kb_id,
                SignalEvent.signal_type == signal_type,
                SignalEvent.is_archived == False,
                SignalEvent.is_dismissed == False,
                func.coalesce(SignalEvent.evidence_date, SignalEvent.detected_at) >= cutoff,
            )
        )
        count = count_result.scalar() or 0
        results.append(count >= min_count)

    return all(results) if operator == "all" else any(results)


async def evaluate_rules_for_company(
    db: AsyncSession,
    user_id: UUID,
    company_kb_id: UUID,
    search_text: str = "",
) -> list[dict]:
    """Evaluate all active custom rules for a company. Returns list of triggered rules."""
    rules = await get_rules_for_user(db, user_id, active_only=True)
    triggered = []

    for rule in rules:
        fired = False

        if rule.rule_type == "keyword":
            fired = evaluate_keyword_rule(rule, search_text)
        elif rule.rule_type == "pattern":
            fired = evaluate_pattern_rule(rule, search_text)
        elif rule.rule_type == "composite":
            fired = await evaluate_composite_rule(db, rule, company_kb_id)

        if fired:
            rule.last_triggered_at = datetime.now(timezone.utc)
            rule.trigger_count = (rule.trigger_count or 0) + 1
            triggered.append({
                "rule_id": str(rule.id),
                "rule_name": rule.name,
                "rule_type": rule.rule_type,
                "signal_type_output": rule.signal_type_output,
                "priority_output": rule.priority_output,
            })

    if triggered:
        await db.flush()

    return triggered
