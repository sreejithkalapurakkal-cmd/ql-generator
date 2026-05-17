"""Background signal detection runner.

Processes signal detection for all companies in a tracking list,
emitting SSE progress events for real-time frontend updates.
Events are also persisted to SignalDetectionLog for replay on page revisit.
"""
import logging
import uuid as uuid_mod
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.models.signal_detection_run import SignalDetectionRun
from app.models.signal_detection_log import SignalDetectionLog
from app.models.tracking_list import TrackingList
from app.models.tracking_list_membership import TrackingListMembership
from app.models.company_knowledge_base import CompanyKnowledgeBase
from app.services import event_store
from app.services.signal_service import (
    detect_signals_for_company,
    recompute_signal_heat_for_company,
)
from app.services.notification_service import create_notification

logger = logging.getLogger(__name__)


async def execute_signal_detection(run_id: UUID) -> None:
    """Background task: detect signals for all companies in a tracking list.

    Opens its own db session (runs outside the request lifecycle).
    Emits SSE events to the event store for real-time progress.
    Persists events to SignalDetectionLog for replay on page revisit.
    """
    run_id_str = str(run_id)
    seq = 0  # sequence counter for log persistence

    logger.info(f"Signal detection task starting for run {run_id}")

    async with async_session() as db:
        try:
            # Load the run record
            result = await db.execute(
                select(SignalDetectionRun).where(SignalDetectionRun.id == run_id)
            )
            run = result.scalar_one_or_none()
            if not run:
                logger.error(f"SignalDetectionRun {run_id} not found")
                return

            # Load tracking list
            result = await db.execute(
                select(TrackingList).where(TrackingList.id == run.tracking_list_id)
            )
            tracking_list = result.scalar_one_or_none()
            if not tracking_list:
                run.status = "failed"
                run.error_log = "Tracking list not found"
                await db.commit()
                return

            # Load members (company kb ids + names)
            members_result = await db.execute(
                select(
                    TrackingListMembership.company_kb_id,
                    CompanyKnowledgeBase.canonical_name,
                    CompanyKnowledgeBase.normalized_domain,
                )
                .join(
                    CompanyKnowledgeBase,
                    TrackingListMembership.company_kb_id == CompanyKnowledgeBase.id,
                )
                .where(TrackingListMembership.tracking_list_id == run.tracking_list_id)
                .limit(20)
            )
            members = members_result.all()

            if not members:
                run.status = "completed"
                run.completed_at = datetime.now(timezone.utc)
                await _emit_and_persist(db, run_id_str, run_id, seq, {
                    "type": "signal_detection_completed",
                    "data": {
                        "signals_detected": 0,
                        "companies_scanned": 0,
                    },
                })
                await db.commit()
                return

            # Update run to running
            run.status = "running"
            run.total_companies = len(members)
            run.started_at = datetime.now(timezone.utc)
            await db.commit()

            hints = tracking_list.signal_hints or {}
            total = len(members)
            total_detected = 0
            high_priority_signals = []

            for i, (kb_id, company_name, domain) in enumerate(members):
                display_name = company_name or domain or "Unknown"

                # Check for cancellation
                if await event_store.is_cancelled(run_id_str):
                    run.status = "cancelled"
                    run.completed_at = datetime.now(timezone.utc)
                    seq = await _emit_and_persist(db, run_id_str, run_id, seq, {
                        "type": "signal_detection_cancelled",
                        "data": {
                            "signals_detected": total_detected,
                            "companies_scanned": i,
                        },
                    })
                    await db.commit()
                    return

                # Emit progress event
                seq = await _emit_and_persist(db, run_id_str, run_id, seq, {
                    "type": "signal_progress",
                    "data": {
                        "company_index": i,
                        "total": total,
                        "company_name": display_name,
                        "percent": round((i / total) * 100),
                        "status": "detecting",
                    },
                })

                # Build event emitter for granular tool-level events
                async def make_emitter(company_idx: int):
                    nonlocal seq

                    async def _emit(event_type: str, data: dict):
                        nonlocal seq
                        seq = await _emit_and_persist(db, run_id_str, run_id, seq, {
                            "type": event_type,
                            "data": {**data, "company_index": company_idx, "total": total},
                        })

                    return _emit

                emitter = await make_emitter(i)

                # Detect signals for this company
                signals_found = 0
                try:
                    new_signals = await detect_signals_for_company(
                        db, kb_id, signal_hints=hints,
                        event_emitter=emitter,
                    )
                    signals_found = len(new_signals)
                    total_detected += signals_found
                    if new_signals:
                        await recompute_signal_heat_for_company(db, kb_id)
                        high_priority_signals.extend(
                            s for s in new_signals if s.priority in ("high", "critical")
                        )
                except Exception as e:
                    logger.warning(f"Signal detection failed for {kb_id}: {e}")

                # Emit per-company result
                seq = await _emit_and_persist(db, run_id_str, run_id, seq, {
                    "type": "company_complete",
                    "data": {
                        "company_index": i,
                        "company_name": display_name,
                        "signals_found": signals_found,
                        "percent": round(((i + 1) / total) * 100),
                    },
                })

                # Update run progress
                run.processed_companies = i + 1
                run.signals_detected = total_detected
                await db.commit()

            # Mark completed
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)

            # Emit terminal event
            await _emit_and_persist(db, run_id_str, run_id, seq, {
                "type": "signal_detection_completed",
                "data": {
                    "signals_detected": total_detected,
                    "companies_scanned": total,
                },
            })

            # Create batch notification
            await create_notification(
                db,
                user_id=run.user_id,
                notification_type="monitoring_complete",
                title=f"Signal scan complete: {total_detected} signals found",
                body=f"Scanned {total} companies in '{tracking_list.name}'",
                link=f"/tracking/{tracking_list.id}",
            )

            # Individual notifications for high/critical signals (cap at 10)
            for signal in high_priority_signals[:10]:
                await create_notification(
                    db,
                    user_id=run.user_id,
                    notification_type="signal_detected",
                    title=f"{signal.signal_type}: {signal.title[:200]}",
                    body=signal.summary[:300] if signal.summary else None,
                    link=f"/tracking/{tracking_list.id}",
                    signal_event_id=signal.id,
                )

            await db.commit()

        except Exception as e:
            logger.error(f"Signal detection run {run_id} failed: {e}", exc_info=True)
            # Use a fresh session for error recovery — the original may be broken
            try:
                async with async_session() as err_db:
                    result = await err_db.execute(
                        select(SignalDetectionRun).where(SignalDetectionRun.id == run_id)
                    )
                    run_record = result.scalar_one_or_none()
                    if run_record:
                        run_record.status = "failed"
                        run_record.error_log = str(e)[:2000]
                        run_record.completed_at = datetime.now(timezone.utc)
                        await err_db.commit()
                await event_store.push_event(run_id_str, {
                    "type": "signal_detection_failed",
                    "data": {"message": str(e)[:500]},
                })
            except Exception:
                logger.error(f"Failed to update run {run_id} status", exc_info=True)


async def _emit_and_persist(
    db: AsyncSession,
    run_id_str: str,
    run_id: UUID,
    seq: int,
    event: dict,
) -> int:
    """Push event to Redis event store and persist to SignalDetectionLog.

    Returns the next sequence number.
    """
    await event_store.push_event(run_id_str, event)
    try:
        db.add(SignalDetectionLog(
            id=uuid_mod.uuid4(),
            signal_detection_run_id=run_id,
            event_type=event["type"],
            event_data=event.get("data", {}),
            sequence_number=seq,
        ))
    except Exception as e:
        logger.warning(f"Failed to persist signal detection log: {e}")
    return seq + 1
