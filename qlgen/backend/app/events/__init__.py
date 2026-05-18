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
