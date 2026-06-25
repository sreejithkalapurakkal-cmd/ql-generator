"""Event system initialization.

Registers default event handlers on app startup.
"""
from app.events.event_bus import bus, Events


def register_default_handlers():
    """Register handlers that wire core services together via the event bus."""

    @bus.on(Events.SIGNAL_DETECTED)
    async def on_signal_detected(payload):
        """Recompute heat score + run correlation when a new signal is detected."""
        from app.db.session import async_session
        company_kb_id = payload.get("company_kb_id")
        if not company_kb_id:
            return
        from uuid import UUID
        async with async_session() as db:
            from app.services.signal_service import recompute_signal_heat_for_company
            await recompute_signal_heat_for_company(db, UUID(company_kb_id))
            await db.commit()

    @bus.on(Events.SIGNAL_DETECTED)
    async def on_signal_run_correlation(payload):
        """Run correlation engine after signal detection."""
        from app.db.session import async_session
        company_kb_id = payload.get("company_kb_id")
        if not company_kb_id:
            return
        from uuid import UUID
        async with async_session() as db:
            from app.services.signal_correlation_engine import correlate_signals_for_company
            await correlate_signals_for_company(db, UUID(company_kb_id))
            await db.commit()

    @bus.on(Events.DRAFT_SENT)
    async def on_draft_sent(payload):
        """When a draft is marked as sent, update the company's open_draft_count."""
        from app.db.session import async_session
        company_kb_id = payload.get("company_kb_id")
        if not company_kb_id:
            return
        from uuid import UUID
        async with async_session() as db:
            from sqlalchemy import select, func
            from app.models.draft import Draft
            from app.models.company_knowledge_base import CompanyKnowledgeBase
            count = (await db.execute(
                select(func.count(Draft.id)).where(
                    Draft.company_kb_id == UUID(company_kb_id),
                    Draft.status == "in_progress",
                )
            )).scalar() or 0
            result = await db.execute(
                select(CompanyKnowledgeBase).where(CompanyKnowledgeBase.id == UUID(company_kb_id))
            )
            kb = result.scalar_one_or_none()
            if kb:
                kb.open_draft_count = count
                await db.commit()

    @bus.on(Events.RESEARCH_COMPLETED)
    async def on_research_completed(payload):
        """Invalidate caches when research completes."""
        from app.services.cache_service import cache_delete_prefix
        company_kb_id = payload.get("company_kb_id")
        if company_kb_id:
            cache_delete_prefix(f"dashboard_stats:")
            cache_delete_prefix(f"activity_stats:{company_kb_id}")

    @bus.on(Events.SOURCE_CHANGED)
    async def on_source_changed(payload):
        """When a source has new content, trigger signal extraction for its company."""
        from app.db.session import async_session
        company_kb_id = payload.get("company_kb_id")
        if not company_kb_id:
            return
        from uuid import UUID
        async with async_session() as db:
            from app.services.signal_service import detect_signals_for_company, DEFAULT_SIGNAL_TYPES
            await detect_signals_for_company(db, UUID(company_kb_id), DEFAULT_SIGNAL_TYPES)
            await db.commit()

    @bus.on(Events.BRIEF_GENERATED)
    async def on_brief_generated(payload):
        """Create notification and update KB flags when a brief is generated."""
        from app.db.session import async_session
        company_kb_id = payload.get("company_kb_id")
        user_id = payload.get("user_id")
        version = payload.get("version")
        company_name = payload.get("company_name", "Company")
        if not company_kb_id or not user_id:
            return
        from uuid import UUID
        async with async_session() as db:
            from app.services.notification_service import create_notification
            await create_notification(
                db,
                user_id=UUID(user_id),
                notification_type="brief_generated",
                title=f"Research brief v{version} ready for {company_name}",
                body=f"A new research brief has been generated with the latest signal intelligence.",
            )
            await db.commit()

    @bus.on(Events.CONTACT_ENRICHED)
    async def on_contact_enriched(payload):
        """Create notification when contact enrichment completes for a company."""
        from app.db.session import async_session
        company_kb_id = payload.get("company_kb_id")
        user_id = payload.get("user_id")
        contacts_found = payload.get("contacts_found", 0)
        company_name = payload.get("company_name", "Company")
        if not company_kb_id or not user_id:
            return
        from uuid import UUID
        async with async_session() as db:
            from app.services.notification_service import create_notification
            await create_notification(
                db,
                user_id=UUID(user_id),
                notification_type="contact_enriched",
                title=f"{contacts_found} contacts enriched for {company_name}",
                body=f"Contact enrichment is complete. Decision makers and stakeholders have been identified.",
            )
            await db.commit()

    @bus.on(Events.RESEARCH_STARTED)
    async def on_research_started(payload):
        """Log a milestone activity event when research begins."""
        from app.db.session import async_session
        job_id = payload.get("job_id")
        company_kb_id = payload.get("company_kb_id")
        company_name = payload.get("company_name", "Company")
        if not job_id or not company_kb_id:
            return
        from uuid import UUID
        async with async_session() as db:
            from app.models.activity_event import ActivityEvent
            db.add(ActivityEvent(
                research_job_id=UUID(job_id),
                company_kb_id=UUID(company_kb_id),
                event_type="research_start",
                event_category="research",
                narrative=f"Research initiated for {company_name}",
                milestone=True,
                verbosity_level="summary",
            ))
            await db.commit()

    @bus.on(Events.MONITORING_COMPLETED)
    async def on_monitoring_completed(payload):
        """Create batch notifications after scheduled monitoring sweep."""
        from app.db.session import async_session
        user_id = payload.get("user_id")
        list_name = payload.get("list_name", "Tracking list")
        signals_detected = payload.get("signals_detected", 0)
        if not user_id or signals_detected == 0:
            return
        from uuid import UUID
        async with async_session() as db:
            from app.services.notification_service import create_notification
            await create_notification(
                db,
                user_id=UUID(user_id),
                notification_type="monitoring_complete",
                title=f"Monitoring complete: {signals_detected} new signals in {list_name}",
                body=f"Scheduled monitoring has detected {signals_detected} new signals.",
            )
            await db.commit()
