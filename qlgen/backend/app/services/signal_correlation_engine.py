"""Signal Correlation Engine.

Detects patterns across multiple signals for a company:
- Multi-signal correlations (e.g., funding + hiring surge = critical opportunity)
- Temporal clustering (multiple signals within a time window)
- Category reinforcement (multiple signals in same category boost priority)

Called after signal detection to identify higher-order patterns.
Creates ActivityEvent entries and optionally upgrades signal priorities.
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal_event import SignalEvent
from app.models.activity_event import ActivityEvent

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# Correlation Rule Definitions
# ──────────────────────────────────────────────────────────────────

CORRELATION_RULES = [
    {
        "id": "funding_plus_hiring",
        "name": "Funding + Hiring Surge",
        "description": "Company received funding AND is actively hiring — strong growth signal",
        "required_types": ["funding", "hiring_surge"],
        "within_days": 60,
        "output_priority": "critical",
        "narrative": "Correlating {company}'s recent funding with hiring surge — indicates active growth investment",
        "boost_strength": 15,
    },
    {
        "id": "exec_change_plus_tech",
        "name": "Executive Change + Tech Adoption",
        "description": "New executive paired with technology changes — transformation underway",
        "required_types": ["executive_change", "tech_adoption"],
        "within_days": 90,
        "output_priority": "high",
        "narrative": "New leadership at {company} coinciding with technology changes — transformation initiative likely",
        "boost_strength": 10,
    },
    {
        "id": "funding_plus_expansion",
        "name": "Funding + Expansion",
        "description": "Funding plus geographic or market expansion — scaling rapidly",
        "required_types": ["funding", "expansion"],
        "within_days": 90,
        "output_priority": "high",
        "narrative": "{company} is expanding after recent funding — accelerated growth phase",
        "boost_strength": 12,
    },
    {
        "id": "triple_threat",
        "name": "Triple Threat (Funding + Hiring + Exec)",
        "description": "Funding, hiring, and executive change all detected — maximum opportunity",
        "required_types": ["funding", "hiring_surge", "executive_change"],
        "within_days": 90,
        "output_priority": "critical",
        "narrative": "Triple correlation at {company}: funding, hiring surge, and executive change — maximum buying readiness",
        "boost_strength": 25,
    },
    {
        "id": "product_plus_partnership",
        "name": "Product Launch + Partnership",
        "description": "New product or feature alongside partnership — expanding reach",
        "required_types": ["product_launch", "partnership"],
        "within_days": 60,
        "output_priority": "high",
        "narrative": "{company} launched a product and formed a partnership — go-to-market acceleration",
        "boost_strength": 10,
    },
    {
        "id": "competitor_churn_plus_hiring",
        "name": "Competitor Churn + Hiring",
        "description": "Competitor losing ground while company hires — competitive displacement opportunity",
        "required_types": ["competitor_churn", "hiring_surge"],
        "within_days": 60,
        "output_priority": "critical",
        "narrative": "Competitor churn signal at {company} paired with hiring surge — displacement opportunity",
        "boost_strength": 20,
    },
]

# Temporal clustering thresholds
CLUSTER_WINDOW_DAYS = 14  # Signals within 14 days are clustered
CLUSTER_MIN_SIGNALS = 3   # Need at least 3 signals to form a cluster
CLUSTER_BOOST = 10         # Strength boost for clustered signals


# ──────────────────────────────────────────────────────────────────
# Main Correlation Functions
# ──────────────────────────────────────────────────────────────────

async def correlate_signals_for_company(
    db: AsyncSession,
    company_kb_id: uuid.UUID,
    company_name: str | None = None,
) -> list[dict]:
    """Run all correlation checks for a company's active signals.

    Returns list of correlation results found.
    """
    # Fetch active signals for this company
    result = await db.execute(
        select(SignalEvent).where(
            SignalEvent.company_kb_id == company_kb_id,
            SignalEvent.is_archived == False,
            SignalEvent.is_dismissed == False,
        ).order_by(SignalEvent.detected_at.desc())
    )
    signals = list(result.scalars().all())

    if len(signals) < 2:
        return []

    display_name = company_name or "Unknown Company"
    correlations_found = []

    # 1. Check rule-based correlations
    for rule in CORRELATION_RULES:
        match = _check_rule_match(signals, rule)
        if match:
            correlation = {
                "rule_id": rule["id"],
                "rule_name": rule["name"],
                "narrative": rule["narrative"].format(company=display_name),
                "matched_signals": [str(s.id) for s in match],
                "output_priority": rule["output_priority"],
                "boost_strength": rule["boost_strength"],
            }
            correlations_found.append(correlation)

            # Create activity event
            db.add(ActivityEvent(
                company_kb_id=company_kb_id,
                event_type="correlation_found",
                event_category="correlation",
                narrative=correlation["narrative"],
                narrative_detail=f"Rule: {rule['name']} — {rule['description']}",
                technical_detail={
                    "rule_id": rule["id"],
                    "matched_signal_ids": correlation["matched_signals"],
                    "boost_strength": rule["boost_strength"],
                },
                confidence=0.8,
                milestone=True,
            ))

            # Boost strength of matched signals
            for sig in match:
                new_strength = min(100.0, (sig.strength or 50.0) + rule["boost_strength"])
                sig.strength = new_strength

    # 2. Check temporal clustering
    clusters = _detect_temporal_clusters(signals)
    for cluster in clusters:
        types_in_cluster = list(set(s.signal_type for s in cluster))
        correlation = {
            "rule_id": "temporal_cluster",
            "rule_name": f"Signal Cluster ({len(cluster)} signals)",
            "narrative": f"{len(cluster)} signals detected for {display_name} within {CLUSTER_WINDOW_DAYS} days — elevated activity",
            "matched_signals": [str(s.id) for s in cluster],
            "signal_types": types_in_cluster,
            "output_priority": "high" if len(cluster) >= 4 else "medium",
        }
        correlations_found.append(correlation)

        db.add(ActivityEvent(
            company_kb_id=company_kb_id,
            event_type="correlation_found",
            event_category="correlation",
            narrative=correlation["narrative"],
            narrative_detail=f"Signal types: {', '.join(types_in_cluster)}",
            technical_detail={
                "cluster_size": len(cluster),
                "signal_types": types_in_cluster,
                "window_days": CLUSTER_WINDOW_DAYS,
            },
            confidence=0.7,
        ))

        # Boost clustered signals
        for sig in cluster:
            new_strength = min(100.0, (sig.strength or 50.0) + CLUSTER_BOOST)
            sig.strength = new_strength

    # 3. Check category reinforcement
    category_boosts = _detect_category_reinforcement(signals)
    for category, boost_signals in category_boosts.items():
        for sig in boost_signals:
            sig.strength = min(100.0, (sig.strength or 50.0) + 5)

    if correlations_found:
        await db.flush()

    return correlations_found


def _check_rule_match(
    signals: list[SignalEvent],
    rule: dict,
) -> list[SignalEvent] | None:
    """Check if a correlation rule matches a set of signals.

    Returns the matched signals or None if no match.
    """
    required_types = set(rule["required_types"])
    within_days = rule["within_days"]
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=within_days)

    # Find recent signals matching each required type
    type_signals: dict[str, list[SignalEvent]] = defaultdict(list)
    for sig in signals:
        event_date = sig.evidence_date or sig.detected_at or sig.created_at
        if event_date and event_date.tzinfo is None:
            event_date = event_date.replace(tzinfo=timezone.utc)
        if event_date and event_date >= cutoff:
            if sig.signal_type in required_types:
                type_signals[sig.signal_type].append(sig)

    # Check all required types are present
    if set(type_signals.keys()) >= required_types:
        # Return the best (highest strength) signal from each type
        matched = []
        for sig_type in required_types:
            candidates = type_signals[sig_type]
            best = max(candidates, key=lambda s: s.strength or 0)
            matched.append(best)
        return matched

    return None


def _detect_temporal_clusters(signals: list[SignalEvent]) -> list[list[SignalEvent]]:
    """Detect clusters of signals occurring within a time window.

    Uses a sliding window approach to find groups of N+ signals
    within CLUSTER_WINDOW_DAYS of each other.
    """
    if len(signals) < CLUSTER_MIN_SIGNALS:
        return []

    # Sort by event date
    dated = []
    for sig in signals:
        event_date = sig.evidence_date or sig.detected_at or sig.created_at
        if event_date:
            if event_date.tzinfo is None:
                event_date = event_date.replace(tzinfo=timezone.utc)
            dated.append((event_date, sig))

    dated.sort(key=lambda x: x[0])

    clusters = []
    used = set()
    window = timedelta(days=CLUSTER_WINDOW_DAYS)

    for i, (date_i, _) in enumerate(dated):
        if i in used:
            continue
        cluster = []
        for j in range(i, len(dated)):
            date_j = dated[j][0]
            if date_j - date_i <= window:
                cluster.append(dated[j][1])
            else:
                break

        if len(cluster) >= CLUSTER_MIN_SIGNALS:
            # Only count unique signal types to avoid noise
            unique_types = len(set(s.signal_type for s in cluster))
            if unique_types >= 2:
                clusters.append(cluster)
                used.update(range(i, i + len(cluster)))

    return clusters


def _detect_category_reinforcement(signals: list[SignalEvent]) -> dict[str, list[SignalEvent]]:
    """Detect when multiple signals in the same category reinforce each other.

    E.g., funding + earnings = financial category reinforcement.
    Returns category → list of signals to boost.
    """
    by_category: dict[str, list[SignalEvent]] = defaultdict(list)
    for sig in signals:
        if sig.signal_category:
            by_category[sig.signal_category].append(sig)

    reinforced = {}
    for category, cat_signals in by_category.items():
        unique_types = len(set(s.signal_type for s in cat_signals))
        if unique_types >= 2 and len(cat_signals) >= 2:
            reinforced[category] = cat_signals

    return reinforced
