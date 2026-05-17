"""Account Brief, Outreach Draft & Company Research API endpoints.

Provides structured brief generation with versioning, draft persistence,
and company firmographic research.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.services.brief_service import (
    generate_structured_brief,
    get_latest_brief,
    get_brief_versions,
    get_brief_by_version,
    generate_brief,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/briefs", tags=["briefs"])


# ─── Brief Revision Schemas ─────────────────────────────────────────────────


class BriefRevisionResponse(BaseModel):
    id: str
    company_kb_id: str
    version: int
    sections: list
    word_count: int | None
    generated_by: str | None
    trigger_signal_id: str | None
    trigger_signal_headline: str | None
    model_id: str | None
    created_at: str | None

    class Config:
        from_attributes = True


def _serialize_revision(rev) -> dict:
    return {
        "id": str(rev.id),
        "company_kb_id": str(rev.company_kb_id),
        "version": rev.version,
        "sections": rev.sections,
        "word_count": rev.word_count,
        "generated_by": rev.generated_by,
        "trigger_signal_id": str(rev.trigger_signal_id) if rev.trigger_signal_id else None,
        "trigger_signal_headline": rev.trigger_signal_headline,
        "model_id": rev.model_id,
        "created_at": rev.created_at.isoformat() if rev.created_at else None,
    }


# ─── Brief Endpoints ────────────────────────────────────────────────────────


@router.get("/{company_kb_id}")
async def get_company_brief(
    company_kb_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get the latest research brief for a company.

    Returns the most recent BriefRevision with structured sections.
    """
    revision = await get_latest_brief(db, company_kb_id)
    if not revision:
        return {"company_kb_id": str(company_kb_id), "brief": None}
    return {"company_kb_id": str(company_kb_id), "brief": _serialize_revision(revision)}


@router.get("/{company_kb_id}/versions")
async def list_brief_versions(
    company_kb_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all brief revisions for a company, newest first."""
    revisions = await get_brief_versions(db, company_kb_id)
    return {
        "company_kb_id": str(company_kb_id),
        "revisions": [_serialize_revision(r) for r in revisions],
    }


@router.get("/{company_kb_id}/versions/{version}")
async def get_brief_version(
    company_kb_id: UUID,
    version: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a specific brief revision by version number."""
    revision = await get_brief_by_version(db, company_kb_id, version)
    if not revision:
        raise HTTPException(404, "Brief version not found")
    return {"company_kb_id": str(company_kb_id), "brief": _serialize_revision(revision)}


class GenerateBriefRequest(BaseModel):
    trigger_signal_id: Optional[str] = None


@router.post("/{company_kb_id}/generate")
async def generate_company_brief_structured(
    company_kb_id: UUID,
    request: GenerateBriefRequest = GenerateBriefRequest(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate a new structured research brief (8 sections with citations).

    Creates a new BriefRevision version. If trigger_signal_id is provided,
    it's recorded as the signal that triggered this brief generation.
    """
    trigger_id = UUID(request.trigger_signal_id) if request.trigger_signal_id else None

    revision = await generate_structured_brief(
        db, company_kb_id,
        trigger_signal_id=trigger_id,
        generated_by="manual",
    )
    if not revision:
        raise HTTPException(404, "Company not found in knowledge base")

    return {
        "company_kb_id": str(company_kb_id),
        "brief": _serialize_revision(revision),
    }


# ─── Legacy brief endpoint (backward compatibility) ─────────────────────────


@router.post("/generate/{company_kb_id}")
async def generate_company_brief_legacy(
    company_kb_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate an account brief (legacy markdown format)."""
    brief_markdown = await generate_brief(db, company_kb_id)
    return {
        "company_kb_id": str(company_kb_id),
        "brief": brief_markdown,
    }


# ─── Outreach Draft Endpoints ───────────────────────────────────────────────


class OutreachDraftRequest(BaseModel):
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    context: Optional[str] = None
    format: str = "email"  # email, linkedin
    tone: str = "direct"  # direct, consultative, formal, casual
    signal_id: Optional[str] = None


class UpdateDraftRequest(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    status: Optional[str] = None  # in_progress, sent, discarded


@router.post("/outreach/{company_kb_id}")
async def generate_outreach(
    company_kb_id: UUID,
    request: OutreachDraftRequest = OutreachDraftRequest(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate a curated outreach draft and persist it."""
    from app.services.outreach_service import generate_outreach_draft
    from app.models.draft import Draft

    draft_text = await generate_outreach_draft(
        db, company_kb_id,
        contact_name=request.contact_name,
        contact_title=request.contact_title,
        context=request.context,
        format=request.format,
        tone=request.tone,
        signal_id=request.signal_id,
    )

    # Parse subject and body from the generated markdown
    subject = None
    body = draft_text
    if "**Subject:**" in draft_text:
        parts = draft_text.split("---", 2)
        if len(parts) >= 2:
            subject_line = parts[0].strip()
            if subject_line.startswith("**Subject:**"):
                subject = subject_line.replace("**Subject:**", "").strip()
            body = parts[1].strip() if len(parts) > 1 else draft_text

    # Persist draft
    signal_uuid = UUID(request.signal_id) if request.signal_id else None
    draft = Draft(
        company_kb_id=company_kb_id,
        signal_id=signal_uuid,
        contact_name=request.contact_name,
        contact_title=request.contact_title,
        format=request.format,
        tone=request.tone,
        subject=subject,
        body=body,
        hooks_used=[],
        status="in_progress",
    )
    db.add(draft)
    await db.commit()
    await db.refresh(draft)

    return {
        "id": str(draft.id),
        "company_kb_id": str(company_kb_id),
        "format": draft.format,
        "tone": draft.tone,
        "subject": draft.subject,
        "body": draft.body,
        "status": draft.status,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
        "raw_markdown": draft_text,
    }


@router.get("/drafts/recent")
async def list_recent_drafts(
    limit: int = Query(10, ge=1, le=50),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List recent drafts across all companies for the current user.

    Used by the dashboard to show a recent drafts preview.
    Requires joining through company_kb → tracking_list_membership → tracking_list to scope to user.
    """
    from sqlalchemy import select
    from app.models.draft import Draft
    from app.models.company_knowledge_base import CompanyKnowledgeBase
    from app.models.tracking_list import TrackingList
    from app.models.tracking_list_membership import TrackingListMembership

    # Get user's tracked company KB IDs
    list_result = await db.execute(
        select(TrackingList.id).where(
            TrackingList.user_id == user.id,
            TrackingList.is_active == True,
        )
    )
    list_ids = [row[0] for row in list_result.all()]
    if not list_ids:
        return {"drafts": [], "total": 0}

    membership_result = await db.execute(
        select(TrackingListMembership.company_kb_id).where(
            TrackingListMembership.tracking_list_id.in_(list_ids)
        ).distinct()
    )
    kb_ids = [row[0] for row in membership_result.all()]
    if not kb_ids:
        return {"drafts": [], "total": 0}

    query = (
        select(Draft, CompanyKnowledgeBase.canonical_name, CompanyKnowledgeBase.normalized_domain)
        .join(CompanyKnowledgeBase, Draft.company_kb_id == CompanyKnowledgeBase.id)
        .where(Draft.company_kb_id.in_(kb_ids))
    )
    if status:
        query = query.where(Draft.status == status)

    query = query.order_by(Draft.created_at.desc()).limit(limit)
    result = await db.execute(query)
    rows = result.all()

    return {
        "drafts": [
            {
                "id": str(d.id),
                "company_kb_id": str(d.company_kb_id),
                "company_name": company_name,
                "domain": domain,
                "signal_id": str(d.signal_id) if d.signal_id else None,
                "contact_name": d.contact_name,
                "format": d.format,
                "tone": d.tone,
                "subject": d.subject,
                "body": d.body[:200] if d.body else None,
                "status": d.status,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d, company_name, domain in rows
        ],
        "total": len(rows),
    }


@router.get("/drafts/{company_kb_id}")
async def list_company_drafts(
    company_kb_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all drafts for a company."""
    from sqlalchemy import select
    from app.models.draft import Draft

    result = await db.execute(
        select(Draft)
        .where(Draft.company_kb_id == company_kb_id)
        .order_by(Draft.created_at.desc())
    )
    drafts = list(result.scalars().all())
    return {
        "company_kb_id": str(company_kb_id),
        "drafts": [
            {
                "id": str(d.id),
                "signal_id": str(d.signal_id) if d.signal_id else None,
                "contact_name": d.contact_name,
                "contact_title": d.contact_title,
                "format": d.format,
                "tone": d.tone,
                "subject": d.subject,
                "body": d.body,
                "hooks_used": d.hooks_used,
                "status": d.status,
                "sent_at": d.sent_at.isoformat() if d.sent_at else None,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in drafts
        ],
    }


@router.patch("/drafts/{draft_id}")
async def update_draft(
    draft_id: UUID,
    request: UpdateDraftRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update a draft's content or status."""
    from sqlalchemy import select
    from app.models.draft import Draft

    result = await db.execute(
        select(Draft).where(Draft.id == draft_id)
    )
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "Draft not found")

    if request.subject is not None:
        draft.subject = request.subject
    if request.body is not None:
        draft.body = request.body
    if request.status is not None:
        draft.status = request.status
        if request.status == "sent":
            draft.sent_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(draft)

    return {
        "id": str(draft.id),
        "status": draft.status,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
    }


# ─── Company Research ────────────────────────────────────────────────────────


@router.post("/research/{company_kb_id}")
async def research_company(
    company_kb_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Research basic firmographic data for a company and fill missing KB fields."""
    from app.services.company_research_service import research_company_info

    result = await research_company_info(db, company_kb_id)
    if result.get("error"):
        raise HTTPException(400, result["error"])

    await db.commit()
    return result


# ─── Export endpoints ──────────────────────────────────────────────────────────


@router.get("/{company_kb_id}/export/html")
async def export_brief_html(
    company_kb_id: UUID,
    version: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Export a research brief as print-ready HTML (save as PDF from browser)."""
    from fastapi.responses import HTMLResponse
    from app.services.signal_export_service import generate_brief_html

    html = await generate_brief_html(db, company_kb_id, version=version)
    return HTMLResponse(content=html)


@router.get("/{company_kb_id}/export/signals")
async def export_signal_report(
    company_kb_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Export a signal report as XLSX."""
    from fastapi.responses import StreamingResponse
    from app.services.signal_export_service import generate_signal_report_xlsx

    buf = await generate_signal_report_xlsx(db, company_kb_id)

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=signal_report_{company_kb_id}.xlsx"},
    )
