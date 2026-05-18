"""Contacts API endpoints.

Provides contact enrichment triggering and retrieval for tracked companies.
"""
import logging
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.company_knowledge_base import CompanyKnowledgeBase

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
    """Trigger async contact enrichment for a company."""
    result = await db.execute(
        select(CompanyKnowledgeBase).where(CompanyKnowledgeBase.id == company_kb_id)
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Company not found")

    # Create a research job for contact enrichment
    from app.services.research_orchestrator import create_research_job
    job = await create_research_job(
        db, company_kb_id, user.id,
        job_type="contact_enrichment",
        research_depth="standard",
    )
    await db.commit()

    return {
        "status": "enrichment_started",
        "job_id": str(job.id),
        "company_kb_id": str(company_kb_id),
    }
