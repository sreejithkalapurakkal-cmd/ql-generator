"""Contacts API endpoints.

Provides contact enrichment triggering and retrieval for tracked companies.
All enrichment operations support async SSE streaming for real-time progress.
"""
import asyncio
import logging
import uuid as uuid_mod
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_current_user, get_user_from_token_param
from app.models.user import User
from app.models.company_knowledge_base import CompanyKnowledgeBase
from app.services import event_store
from app.api.sse_helpers import create_sse_stream

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("/{company_kb_id}")
async def get_contacts(
    company_kb_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get contacts for a company from the knowledge base."""
    result = await db.execute(
        select(CompanyKnowledgeBase).where(CompanyKnowledgeBase.id == company_kb_id)
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Company not found")

    contacts = kb.best_known_contacts or []
    enriched = []
    for i, c in enumerate(contacts):
        enriched.append({
            "id": c.get("id", str(i)),
            "name": c.get("full_name") or c.get("name", "Unknown"),
            "title": c.get("designation") or c.get("title", ""),
            "email": c.get("email"),
            "linkedin_url": c.get("linkedin_url"),
            "phone": c.get("phone"),
            "is_primary": i == 0,
            "is_eu_resident": c.get("is_eu_resident", False),
            "influence_level": c.get("influence_level", "unknown"),
            "department": c.get("department"),
            "enrichment_source": c.get("source"),
            "enrichment_confidence": c.get("confidence"),
        })

    return {
        "contacts": enriched,
        "total": len(enriched),
        "company_kb_id": str(company_kb_id),
    }


@router.post("/{company_kb_id}/enrich")
async def trigger_contact_enrichment(
    company_kb_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Trigger async contact enrichment for a company.

    Returns a run_id for SSE streaming of enrichment progress.
    Connect to /contacts/{company_kb_id}/enrich/stream/{run_id}?token=... for real-time updates.
    """
    result = await db.execute(
        select(CompanyKnowledgeBase).where(CompanyKnowledgeBase.id == company_kb_id)
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Company not found")

    run_id = str(uuid_mod.uuid4())
    await event_store.init_run(run_id)

    asyncio.create_task(
        _run_contact_enrichment_bg(
            run_id, company_kb_id, user.id,
            company_name=kb.canonical_name or kb.normalized_domain or "Unknown",
        )
    )

    return {
        "status": "enrichment_started",
        "run_id": run_id,
        "company_kb_id": str(company_kb_id),
    }


@router.get("/{company_kb_id}/enrich/stream/{run_id}")
async def stream_contact_enrichment(
    company_kb_id: UUID,
    run_id: str,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_user_from_token_param),
):
    """SSE stream for single-company contact enrichment progress."""
    return create_sse_stream(
        run_id,
        terminal_events={"enrichment_complete", "enrichment_failed"},
    )


async def _run_contact_enrichment_bg(
    run_id: str,
    company_kb_id: UUID,
    user_id: UUID,
    company_name: str,
) -> None:
    """Background task: enrich contacts for a single company with SSE progress."""
    from app.db.session import async_session
    from app.services.research_orchestrator import create_research_job, execute_research_job

    try:
        await event_store.push_event(run_id, {
            "type": "enrichment_started",
            "data": {"company_name": company_name},
        })

        await event_store.push_event(run_id, {
            "type": "agent_thought",
            "data": {"message": f"Starting contact enrichment for {company_name}..."},
        })

        await event_store.push_event(run_id, {
            "type": "progress",
            "data": {"percent": 10, "label": "Creating enrichment research job..."},
        })

        async with async_session() as db:
            job = await create_research_job(
                db, company_kb_id, user_id,
                job_type="contact_enrichment",
                research_depth="standard",
            )
            await db.commit()

        await event_store.push_event(run_id, {
            "type": "agent_thought",
            "data": {"message": "Searching for decision makers and stakeholders..."},
        })

        await event_store.push_event(run_id, {
            "type": "tool_start",
            "data": {"tool": "executive_intel", "label": "Finding executives and contacts..."},
        })

        await event_store.push_event(run_id, {
            "type": "progress",
            "data": {"percent": 30, "label": "Discovering contacts via research agents..."},
        })

        # Execute the research job (this runs its own stages internally)
        await execute_research_job(job.id)

        await event_store.push_event(run_id, {
            "type": "progress",
            "data": {"percent": 90, "label": "Loading enriched contacts..."},
        })

        # Fetch updated contacts
        async with async_session() as db:
            result = await db.execute(
                select(CompanyKnowledgeBase).where(CompanyKnowledgeBase.id == company_kb_id)
            )
            kb = result.scalar_one_or_none()
            contacts = (kb.best_known_contacts or []) if kb else []

        await event_store.push_event(run_id, {
            "type": "enrichment_complete",
            "data": {
                "company_kb_id": str(company_kb_id),
                "company_name": company_name,
                "contacts_found": len(contacts),
                "job_id": str(job.id),
            },
        })

    except Exception as e:
        logger.error(f"Contact enrichment background task failed: {e}", exc_info=True)
        await event_store.push_event(run_id, {
            "type": "enrichment_failed",
            "data": {"message": "Contact enrichment failed. Please try again."},
        })
