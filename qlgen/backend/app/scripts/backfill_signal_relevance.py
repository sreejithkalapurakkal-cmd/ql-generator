"""Backfill LLM relevance verdicts for existing signals.

Evaluates signals that have not yet been relevance-checked (is_relevant IS NULL)
and that could currently surface (not archived/dismissed), grouping by company so
each company's signals are judged together. Sets is_relevant / relevance_reason /
relevance_checked_at. Non-destructive: rows judged irrelevant are flagged (and then
hidden by the surfacing filters), never deleted or archived.

Usage:
    python -m app.scripts.backfill_signal_relevance [--limit N] [--dry-run]
"""
import asyncio
import os
import sys
from pathlib import Path

# Ensure backend dir is on sys.path (mirrors app/scripts/seed_admin.py)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import async_session
from app.models.signal_event import SignalEvent
from app.models.company_knowledge_base import CompanyKnowledgeBase
from app.services.signal_relevance_service import verify_signal_relevance
from app.services.signal_service import _clean_company_name

# Judge at most this many of a company's signals per LLM call.
_BATCH = 10


def _to_candidate(signal: SignalEvent) -> dict:
    return {
        "title": signal.title,
        "summary": signal.summary,
        "source_url": signal.source_url,
        "evidence": signal.evidence,
    }


async def backfill(limit: int | None, dry_run: bool) -> None:
    async with async_session() as db:
        # Pull unchecked, currently-surfaceable signals joined with their company.
        query = (
            select(SignalEvent, CompanyKnowledgeBase)
            .join(CompanyKnowledgeBase, SignalEvent.company_kb_id == CompanyKnowledgeBase.id)
            .where(
                SignalEvent.is_relevant.is_(None),
                SignalEvent.is_archived == False,
                SignalEvent.is_dismissed == False,
            )
            .order_by(SignalEvent.company_kb_id)
        )
        if limit:
            query = query.limit(limit)

        rows = (await db.execute(query)).all()
        if not rows:
            print("No unchecked signals to backfill.")
            return

        # Group signals by company.
        by_company: dict = {}
        for signal, kb in rows:
            by_company.setdefault(kb.id, {"kb": kb, "signals": []})["signals"].append(signal)

        total = len(rows)
        print(f"Backfilling {total} signal(s) across {len(by_company)} company(ies)"
              f"{' (dry-run)' if dry_run else ''}...")

        checked = 0
        irrelevant = 0
        checked_at = datetime.now(timezone.utc)

        for entry in by_company.values():
            kb = entry["kb"]
            signals = entry["signals"]
            raw_name = kb.canonical_name or kb.normalized_domain or ""
            domain = kb.normalized_domain or ""
            company_name = _clean_company_name(raw_name, domain)

            for i in range(0, len(signals), _BATCH):
                chunk = signals[i:i + _BATCH]
                verdicts = await verify_signal_relevance(
                    company_name, domain, [_to_candidate(s) for s in chunk]
                )
                for signal, verdict in zip(chunk, verdicts):
                    rel = verdict.get("relevant")
                    checked += 1
                    if rel is False:
                        irrelevant += 1
                    if not dry_run:
                        signal.is_relevant = rel
                        signal.relevance_reason = verdict.get("reason")
                        signal.relevance_checked_at = checked_at
                print(f"  {company_name}: judged {len(chunk)} "
                      f"({sum(1 for _, v in zip(chunk, verdicts) if v.get('relevant') is False)} irrelevant)")

            if not dry_run:
                await db.commit()

        print(f"Done. Checked {checked} signal(s); {irrelevant} judged irrelevant "
              f"(now hidden){' [dry-run, nothing saved]' if dry_run else ''}.")


def main() -> None:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    limit = None
    if "--limit" in args:
        idx = args.index("--limit")
        if idx + 1 < len(args):
            limit = int(args[idx + 1])
    asyncio.run(backfill(limit, dry_run))


if __name__ == "__main__":
    main()
