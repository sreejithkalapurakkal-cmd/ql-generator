"""Confidence Scoring Service.

Multi-factor confidence assessment for signals based on:
1. Source authority (SEC filing > press release > blog > web change)
2. Corroboration count (multiple sources = higher confidence)
3. Source recency (recent = higher)
4. Source class diversity (multiple types = higher)

Wire into signal detection to auto-score new signals.
"""
import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal_event import SignalEvent

logger = logging.getLogger(__name__)

# Source authority weights (0-1)
SOURCE_AUTHORITY = {
    "sec_filing": 0.90,
    "earnings_call": 0.85,
    "press_release": 0.80,
    "government_registry": 0.80,
    "apollo": 0.75,
    "hiring_signal": 0.70,
    "financial_data": 0.70,
    "news_article": 0.60,
    "exa_search": 0.55,
    "tavily_search": 0.55,
    "web_scraper": 0.40,
    "duckduckgo_search": 0.35,
    "web_change": 0.30,
    "social_media": 0.20,
    "forum": 0.15,
}

# Default authority for unknown sources
DEFAULT_AUTHORITY = 0.35


def compute_confidence(
    source_tool: str | None = None,
    source_class: str | None = None,
    evidence: dict | None = None,
    evidence_date: datetime | None = None,
    strength: float = 50.0,
) -> tuple[str, float]:
    """Compute confidence level for a signal.

    Returns (confidence_label, confidence_score) where:
    - confidence_label: "high", "medium", or "low"
    - confidence_score: 0.0-1.0 numeric score

    Factors:
    1. Source authority (40% weight)
    2. Corroboration (25% weight)
    3. Recency (20% weight)
    4. Source diversity (15% weight)
    """
    score = 0.0

    # 1. Source authority (0.4 weight)
    authority = SOURCE_AUTHORITY.get(source_tool or "", DEFAULT_AUTHORITY)
    if source_class:
        class_authority = SOURCE_AUTHORITY.get(source_class, DEFAULT_AUTHORITY)
        authority = max(authority, class_authority)
    score += authority * 0.4

    # 2. Corroboration count (0.25 weight)
    evidence = evidence or {}
    articles = evidence.get("articles", [])
    corroboration_count = len(articles)
    if evidence.get("corroboration_count"):
        corroboration_count = max(corroboration_count, evidence["corroboration_count"])

    if corroboration_count >= 3:
        score += 0.25
    elif corroboration_count >= 2:
        score += 0.15
    elif corroboration_count >= 1:
        score += 0.08

    # 3. Recency (0.2 weight)
    if evidence_date:
        now = datetime.now(timezone.utc)
        if evidence_date.tzinfo is None:
            evidence_date = evidence_date.replace(tzinfo=timezone.utc)
        age_days = (now - evidence_date).days

        if age_days <= 7:
            score += 0.20  # Very fresh
        elif age_days <= 14:
            score += 0.15
        elif age_days <= 30:
            score += 0.10
        elif age_days <= 90:
            score += 0.05
        # >90 days: no recency bonus

    # 4. Source diversity (0.15 weight)
    source_classes = set()
    for article in articles:
        for key in ("source_tool", "source_class", "source"):
            if article.get(key):
                source_classes.add(article[key])
    if source_tool:
        source_classes.add(source_tool)
    if source_class:
        source_classes.add(source_class)

    if len(source_classes) >= 3:
        score += 0.15
    elif len(source_classes) >= 2:
        score += 0.10
    elif len(source_classes) >= 1:
        score += 0.05

    # Normalize to 0-1
    score = min(1.0, max(0.0, score))

    # Map to label
    if score >= 0.65:
        label = "high"
    elif score >= 0.35:
        label = "medium"
    else:
        label = "low"

    return label, round(score, 3)


async def score_signal(db: AsyncSession, signal: SignalEvent) -> str:
    """Score a single signal's confidence and update the record.

    Returns the confidence label.
    """
    label, score = compute_confidence(
        source_tool=signal.source_tool,
        source_class=signal.source_class,
        evidence=signal.evidence,
        evidence_date=signal.evidence_date,
        strength=signal.strength or 50.0,
    )
    signal.confidence = label
    return label


async def score_company_signals(db: AsyncSession, company_kb_id: UUID) -> int:
    """Score all unscored signals for a company. Returns count scored."""
    result = await db.execute(
        select(SignalEvent).where(
            SignalEvent.company_kb_id == company_kb_id,
            SignalEvent.confidence.is_(None),
            SignalEvent.is_archived == False,
        )
    )
    signals = list(result.scalars().all())

    scored = 0
    for signal in signals:
        await score_signal(db, signal)
        scored += 1

    if scored > 0:
        await db.flush()

    return scored


def score_inline(
    source_tool: str | None,
    evidence: dict | None,
    evidence_date: datetime | None,
) -> str:
    """Quick inline confidence scoring for use during signal creation.

    Returns confidence label without DB access.
    """
    label, _ = compute_confidence(
        source_tool=source_tool,
        evidence=evidence,
        evidence_date=evidence_date,
    )
    return label
