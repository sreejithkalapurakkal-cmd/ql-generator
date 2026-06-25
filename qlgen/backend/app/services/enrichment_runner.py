"""Background contact enrichment runner.

Processes contact enrichment for all companies in a tracking list,
emitting SSE progress events for real-time frontend updates.
Events are also persisted to EnrichmentLog for replay on page revisit.
"""
import logging
import uuid as uuid_mod
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.models.enrichment_run import EnrichmentRun
from app.models.enrichment_log import EnrichmentLog
from app.models.tracking_list import TrackingList
from app.models.tracking_list_membership import TrackingListMembership
from app.models.company_knowledge_base import CompanyKnowledgeBase
from app.services import event_store
from app.services.enrichment_service import enrich_company_contacts
from app.services.notification_service import create_notification

logger = logging.getLogger(__name__)


async def execute_enrichment(run_id: UUID) -> None:
    """Background task: enrich contacts for all companies in a tracking list.

    Opens its own db session (runs outside the request lifecycle).
    Emits SSE events to the event store for real-time progress.
    Persists events to EnrichmentLog for replay on page revisit.
    """
    run_id_str = str(run_id)
    seq = 0

    logger.info(f"Enrichment task starting for run {run_id}")

    async with async_session() as db:
        try:
            # Load the run record
            result = await db.execute(
                select(EnrichmentRun).where(EnrichmentRun.id == run_id)
            )
            run = result.scalar_one_or_none()
            if not run:
                logger.error(f"EnrichmentRun {run_id} not found")
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

            # Load members with company info
            members_result = await db.execute(
                select(
                    TrackingListMembership,
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
                    "type": "enrichment_completed",
                    "data": {
                        "total_contacts": 0,
                        "companies_enriched": 0,
                    },
                })
                await db.commit()
                return

            # Update run to running
            run.status = "running"
            run.total_companies = len(members)
            run.started_at = datetime.now(timezone.utc)
            await db.commit()

            target_roles = run.target_roles
            total = len(members)
            total_contacts = 0

            for i, (membership, company_name, domain) in enumerate(members):
                display_name = company_name or domain or "Unknown"

                # Check for cancellation
                if await event_store.is_cancelled(run_id_str):
                    run.status = "cancelled"
                    run.completed_at = datetime.now(timezone.utc)
                    seq = await _emit_and_persist(db, run_id_str, run_id, seq, {
                        "type": "enrichment_cancelled",
                        "data": {
                            "total_contacts": total_contacts,
                            "companies_enriched": i,
                        },
                    })
                    await db.commit()
                    return

                # Emit progress event
                seq = await _emit_and_persist(db, run_id_str, run_id, seq, {
                    "type": "enrichment_progress",
                    "data": {
                        "company_index": i,
                        "total": total,
                        "company_name": display_name,
                        "percent": round((i / total) * 100),
                        "status": "enriching",
                    },
                })

                membership.enrichment_status = "in_progress"
                await db.flush()

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

                contacts_for_company = 0
                try:
                    enrichment = await enrich_company_contacts(
                        db, membership.company_kb_id,
                        target_roles=target_roles,
                        event_emitter=emitter,
                    )
                    contacts_for_company = enrichment.get("contacts_found", 0)
                    total_contacts += enrichment.get("total_contacts", 0)
                    membership.enrichment_status = "enriched"
                except Exception as e:
                    logger.warning(f"Enrichment failed for {membership.company_kb_id}: {e}")
                    membership.enrichment_status = "failed"

                # Emit per-company result
                seq = await _emit_and_persist(db, run_id_str, run_id, seq, {
                    "type": "company_complete",
                    "data": {
                        "company_index": i,
                        "company_name": display_name,
                        "contacts_for_company": contacts_for_company,
                        "total_contacts": total_contacts,
                        "percent": round(((i + 1) / total) * 100),
                    },
                })

                # Update run progress
                run.processed_companies = i + 1
                run.contacts_found = total_contacts
                await db.commit()

            # Mark completed
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)

            companies_enriched = sum(
                1 for m, _, _ in members if m.enrichment_status == "enriched"
            )

            # Emit terminal event
            await _emit_and_persist(db, run_id_str, run_id, seq, {
                "type": "enrichment_completed",
                "data": {
                    "total_contacts": total_contacts,
                    "companies_enriched": companies_enriched,
                },
            })

            # Create notification
            await create_notification(
                db,
                user_id=run.user_id,
                notification_type="monitoring_complete",
                title=f"Contact enrichment complete: {total_contacts} contacts found",
                body=f"Enriched {companies_enriched} companies in '{tracking_list.name}'",
                link=f"/tracking/{tracking_list.id}",
            )

            await db.commit()

            # Emit event bus event for cross-service reactions
            from app.events.event_bus import bus, Events
            await bus.emit(Events.CONTACT_ENRICHED, {
                "user_id": str(run.user_id),
                "tracking_list_id": str(tracking_list.id),
                "company_name": tracking_list.name,
                "contacts_found": total_contacts,
            })

        except Exception as e:
            logger.error(f"Enrichment run {run_id} failed: {e}", exc_info=True)
            # Use a fresh session for error recovery — the original may be broken
            try:
                async with async_session() as err_db:
                    result = await err_db.execute(
                        select(EnrichmentRun).where(EnrichmentRun.id == run_id)
                    )
                    run_record = result.scalar_one_or_none()
                    if run_record:
                        run_record.status = "failed"
                        run_record.error_log = str(e)[:2000]
                        run_record.completed_at = datetime.now(timezone.utc)
                        await err_db.commit()
                await event_store.push_event(run_id_str, {
                    "type": "enrichment_failed",
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
    """Push event to Redis event store and persist to EnrichmentLog.

    Returns the next sequence number.
    """
    await event_store.push_event(run_id_str, event)
    try:
        db.add(EnrichmentLog(
            id=uuid_mod.uuid4(),
            enrichment_run_id=run_id,
            event_type=event["type"],
            event_data=event.get("data", {}),
            sequence_number=seq,
        ))
    except Exception as e:
        logger.warning(f"Failed to persist enrichment log: {e}")
    return seq + 1
