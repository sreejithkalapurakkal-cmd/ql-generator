"""Account Brief, Outreach Draft & Company Research API endpoints.

Provides structured brief generation with versioning, draft persistence,
and company firmographic research.  All agent-driven operations support
async background execution with SSE streaming for real-time progress.
"""
import asyncio
import logging
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.db.session import get_db
from app.auth.dependencies import get_current_user, get_user_from_token_param
from app.models.user import User
from app.services.brief_service import (
    generate_structured_brief,
    get_latest_brief,
    get_brief_versions,
    get_brief_by_version,
    generate_brief,
)
from app.services import event_store
from app.api.sse_helpers import create_sse_stream

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


class OutreachDraftRequest(BaseModel):
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    context: Optional[str] = None
    format: str = "email"  # email, linkedin
    tone: str = "direct"  # direct, consultative, formal, casual
    signal_id: Optional[str] = None


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


@router.post("/{company_kb_id}/generate-stream")
async def generate_brief_stream(
    company_kb_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate a structured brief with SSE streaming per section.

    Note: Uses its own DB session inside the generator to avoid
    the request-scoped session being closed before the generator completes.
    """
    import json
    import asyncio
    from sqlalchemy import select
    from app.models.company_knowledge_base import CompanyKnowledgeBase
    from app.db.session import async_session as make_session

    # Validate company exists using the request-scoped session (before streaming starts)
    result = await db.execute(
        select(CompanyKnowledgeBase.id, CompanyKnowledgeBase.canonical_name)
        .where(CompanyKnowledgeBase.id == company_kb_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Company not found")
    company_name = row[1]

    async def event_stream():
        try:
            yield f"data: {json.dumps({'type': 'brief_started', 'company': company_name})}\n\n"

            # Use a fresh session that outlives the request lifecycle
            async with make_session() as gen_db:
                revision = await generate_structured_brief(gen_db, company_kb_id)
                if not revision:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to generate brief'})}\n\n"
                    return

                sections = revision.sections or []

                for i, section in enumerate(sections):
                    yield f"data: {json.dumps({'type': 'section_started', 'section_id': section.get('id', str(i)), 'heading': section.get('heading', ''), 'index': i})}\n\n"
                    await asyncio.sleep(0.1)
                    yield f"data: {json.dumps({'type': 'section_complete', 'section': section, 'index': i})}\n\n"

                yield f"data: {json.dumps({'type': 'brief_ready', 'version': revision.version, 'word_count': revision.word_count, 'section_count': len(sections)})}\n\n"
        except Exception as e:
            logger.error(f"Brief stream generation failed: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': 'Brief generation failed. Please try again.'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ─── Async Brief Generation (SSE) ──────────────────────────────────────────


@router.post("/{company_kb_id}/generate/start")
async def start_brief_generation(
    company_kb_id: UUID,
    request: GenerateBriefRequest = GenerateBriefRequest(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start brief generation as a background task with SSE progress.

    Returns a run_id that can be used to connect to the SSE stream.
    """
    from sqlalchemy import select
    from app.models.company_knowledge_base import CompanyKnowledgeBase

    result = await db.execute(
        select(CompanyKnowledgeBase).where(CompanyKnowledgeBase.id == company_kb_id)
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Company not found")

    run_id = str(uuid_mod.uuid4())
    await event_store.init_run(run_id)

    trigger_id = UUID(request.trigger_signal_id) if request.trigger_signal_id else None

    asyncio.create_task(
        _run_brief_generation_bg(run_id, company_kb_id, trigger_id, kb.canonical_name or kb.normalized_domain)
    )

    return {"run_id": run_id, "status": "started", "company_kb_id": str(company_kb_id)}


@router.get("/{company_kb_id}/generate/stream/{run_id}")
async def stream_brief_generation(
    company_kb_id: UUID,
    run_id: str,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_user_from_token_param),
):
    """SSE stream for brief generation progress."""
    return create_sse_stream(
        run_id,
        terminal_events={"brief_ready", "brief_failed"},
    )


async def _run_brief_generation_bg(
    run_id: str,
    company_kb_id: UUID,
    trigger_signal_id: UUID | None,
    company_name: str,
) -> None:
    """Background task: generate a structured brief with SSE progress events."""
    from app.db.session import async_session
    from app.services.brief_service import BRIEF_SECTIONS

    try:
        await event_store.push_event(run_id, {
            "type": "brief_started",
            "data": {"company_name": company_name, "total_sections": len(BRIEF_SECTIONS)},
        })

        await event_store.push_event(run_id, {
            "type": "agent_thought",
            "data": {"message": f"Gathering company data and recent signals for {company_name}..."},
        })

        async with async_session() as db:
            # Emit progress: data gathering
            await event_store.push_event(run_id, {
                "type": "progress",
                "data": {"percent": 10, "label": "Collecting company intelligence..."},
            })

            # Generate the brief
            await event_store.push_event(run_id, {
                "type": "agent_thought",
                "data": {"message": "Calling LLM to generate 8-section research brief..."},
            })

            await event_store.push_event(run_id, {
                "type": "progress",
                "data": {"percent": 20, "label": "Generating research brief via AI..."},
            })

            revision = await generate_structured_brief(
                db, company_kb_id,
                trigger_signal_id=trigger_signal_id,
                generated_by="manual",
            )

            if not revision:
                await event_store.push_event(run_id, {
                    "type": "brief_failed",
                    "data": {"message": "Company not found in knowledge base"},
                })
                return

            # Stream sections progressively
            sections = revision.sections or []
            for i, section in enumerate(sections):
                pct = 30 + int((i / max(len(sections), 1)) * 60)
                await event_store.push_event(run_id, {
                    "type": "section_complete",
                    "data": {
                        "section_id": section.get("id", str(i)),
                        "heading": section.get("heading", ""),
                        "index": i,
                        "total": len(sections),
                        "percent": pct,
                        "confidence": section.get("confidence", 0),
                        "insufficient": section.get("insufficient", False),
                    },
                })

            await event_store.push_event(run_id, {
                "type": "progress",
                "data": {"percent": 95, "label": "Finalizing brief..."},
            })

            # Terminal event
            await event_store.push_event(run_id, {
                "type": "brief_ready",
                "data": {
                    "version": revision.version,
                    "word_count": revision.word_count,
                    "section_count": len(sections),
                    "company_kb_id": str(company_kb_id),
                },
            })

    except Exception as e:
        logger.error(f"Brief generation background task failed: {e}", exc_info=True)
        await event_store.push_event(run_id, {
            "type": "brief_failed",
            "data": {"message": "Brief generation failed. Please try again."},
        })


# ─── Async Outreach Draft Generation (SSE) ────────────────────────────────


@router.post("/outreach/{company_kb_id}/start")
async def start_outreach_generation(
    company_kb_id: UUID,
    request: OutreachDraftRequest = OutreachDraftRequest(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start outreach draft generation as a background task with SSE progress.

    Returns a run_id for SSE streaming.
    """
    from sqlalchemy import select
    from app.models.company_knowledge_base import CompanyKnowledgeBase

    result = await db.execute(
        select(CompanyKnowledgeBase).where(CompanyKnowledgeBase.id == company_kb_id)
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Company not found")

    run_id = str(uuid_mod.uuid4())
    await event_store.init_run(run_id)

    asyncio.create_task(
        _run_outreach_generation_bg(
            run_id, company_kb_id,
            company_name=kb.canonical_name or kb.normalized_domain or "Unknown",
            contact_name=request.contact_name,
            contact_title=request.contact_title,
            context=request.context,
            format=request.format,
            tone=request.tone,
            signal_id=request.signal_id,
        )
    )

    return {"run_id": run_id, "status": "started", "company_kb_id": str(company_kb_id)}


@router.get("/outreach/{company_kb_id}/stream/{run_id}")
async def stream_outreach_generation(
    company_kb_id: UUID,
    run_id: str,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_user_from_token_param),
):
    """SSE stream for outreach draft generation progress."""
    return create_sse_stream(
        run_id,
        terminal_events={"outreach_ready", "outreach_failed"},
    )


async def _run_outreach_generation_bg(
    run_id: str,
    company_kb_id: UUID,
    company_name: str,
    contact_name: str | None,
    contact_title: str | None,
    context: str | None,
    format: str,
    tone: str,
    signal_id: str | None,
) -> None:
    """Background task: generate an outreach draft with SSE progress."""
    from app.db.session import async_session
    from app.services.outreach_service import generate_outreach_draft
    from app.models.draft import Draft

    try:
        await event_store.push_event(run_id, {
            "type": "outreach_started",
            "data": {"company_name": company_name, "format": format, "tone": tone},
        })

        await event_store.push_event(run_id, {
            "type": "agent_thought",
            "data": {"message": f"Gathering signals and contact data for {company_name}..."},
        })

        await event_store.push_event(run_id, {
            "type": "progress",
            "data": {"percent": 15, "label": "Loading company intelligence..."},
        })

        async with async_session() as db:
            await event_store.push_event(run_id, {
                "type": "agent_thought",
                "data": {"message": f"Crafting personalized {format} draft with {tone} tone..."},
            })

            await event_store.push_event(run_id, {
                "type": "progress",
                "data": {"percent": 30, "label": f"Generating {format} draft via AI..."},
            })

            draft_result = await generate_outreach_draft(
                db, company_kb_id,
                contact_name=contact_name,
                contact_title=contact_title,
                context=context,
                format=format,
                tone=tone,
                signal_id=signal_id,
            )

            await event_store.push_event(run_id, {
                "type": "progress",
                "data": {"percent": 75, "label": "Saving draft..."},
            })

            draft_text = draft_result["primary"]

            # Parse subject/body
            subject = None
            body = draft_text
            if "**Subject:**" in draft_text:
                parts = draft_text.split("---", 2)
                if len(parts) >= 2:
                    subject_line = parts[0].strip()
                    if subject_line.startswith("**Subject:**"):
                        subject = subject_line.replace("**Subject:**", "").strip()
                    body = parts[1].strip() if len(parts) > 1 else draft_text

            signal_uuid = UUID(signal_id) if signal_id else None
            draft = Draft(
                company_kb_id=company_kb_id,
                signal_id=signal_uuid,
                contact_name=contact_name,
                contact_title=contact_title,
                format=format,
                tone=tone,
                subject=subject,
                body=body,
                hooks_used=[],
                status="in_progress",
            )
            db.add(draft)
            await db.commit()
            await db.refresh(draft)

            await event_store.push_event(run_id, {
                "type": "agent_thought",
                "data": {"message": "Draft generated successfully. Checking for banned phrases..."},
            })

            await event_store.push_event(run_id, {
                "type": "progress",
                "data": {"percent": 95, "label": "Finalizing draft..."},
            })

            # Terminal event
            await event_store.push_event(run_id, {
                "type": "outreach_ready",
                "data": {
                    "draft_id": str(draft.id),
                    "company_kb_id": str(company_kb_id),
                    "format": draft.format,
                    "tone": draft.tone,
                    "subject": draft.subject,
                    "body": draft.body,
                    "status": draft.status,
                    "raw_markdown": draft_text,
                    "template_used": draft_result.get("template_used"),
                    "template_hint": draft_result.get("template_hint"),
                    "drafts": draft_result.get("drafts", []),
                },
            })

    except Exception as e:
        logger.error(f"Outreach generation background task failed: {e}", exc_info=True)
        await event_store.push_event(run_id, {
            "type": "outreach_failed",
            "data": {"message": "Outreach draft generation failed. Please try again."},
        })


# ─── Async Company Research (SSE) ─────────────────────────────────────────


@router.post("/research/{company_kb_id}/start")
async def start_research(
    company_kb_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start company research as a background task with SSE progress.

    Returns a run_id for SSE streaming.
    """
    from sqlalchemy import select
    from app.models.company_knowledge_base import CompanyKnowledgeBase

    result = await db.execute(
        select(CompanyKnowledgeBase).where(CompanyKnowledgeBase.id == company_kb_id)
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Company not found")

    run_id = str(uuid_mod.uuid4())
    await event_store.init_run(run_id)

    asyncio.create_task(
        _run_company_research_bg(
            run_id, company_kb_id,
            company_name=kb.canonical_name or kb.normalized_domain or "Unknown",
        )
    )

    return {"run_id": run_id, "status": "started", "company_kb_id": str(company_kb_id)}


@router.get("/research/{company_kb_id}/stream/{run_id}")
async def stream_research(
    company_kb_id: UUID,
    run_id: str,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_user_from_token_param),
):
    """SSE stream for company research progress."""
    return create_sse_stream(
        run_id,
        terminal_events={"research_complete", "research_failed"},
    )


async def _run_company_research_bg(
    run_id: str,
    company_kb_id: UUID,
    company_name: str,
) -> None:
    """Background task: research company firmographic data with SSE progress."""
    from app.db.session import async_session
    from app.services.company_research_service import research_company_info

    try:
        await event_store.push_event(run_id, {
            "type": "research_started",
            "data": {"company_name": company_name},
        })

        await event_store.push_event(run_id, {
            "type": "agent_thought",
            "data": {"message": f"Beginning firmographic research for {company_name}..."},
        })

        await event_store.push_event(run_id, {
            "type": "tool_start",
            "data": {"tool": "apollo_company_search", "label": "Searching Apollo database..."},
        })

        await event_store.push_event(run_id, {
            "type": "progress",
            "data": {"percent": 15, "label": "Querying Apollo firmographic database..."},
        })

        async with async_session() as db:
            # We can't easily break apart research_company_info into stages
            # with events mid-execution, so we emit before/after the main call.
            # The service itself runs Apollo → web research sequentially.

            await event_store.push_event(run_id, {
                "type": "progress",
                "data": {"percent": 30, "label": "Running multi-source research..."},
            })

            await event_store.push_event(run_id, {
                "type": "agent_thought",
                "data": {"message": "Cross-referencing Apollo data with web sources (DuckDuckGo, LinkedIn, team pages)..."},
            })

            result = await research_company_info(db, company_kb_id)

            if result.get("error"):
                await event_store.push_event(run_id, {
                    "type": "research_failed",
                    "data": {"message": result["error"]},
                })
                return

            await db.commit()

            fields_updated = result.get("fields_updated", [])
            if fields_updated:
                await event_store.push_event(run_id, {
                    "type": "tool_result",
                    "data": {
                        "tool": "company_research",
                        "label": f"Updated {len(fields_updated)} fields: {', '.join(fields_updated)}",
                        "fields_updated": fields_updated,
                    },
                })

            await event_store.push_event(run_id, {
                "type": "progress",
                "data": {"percent": 95, "label": "Research complete"},
            })

            # Terminal event
            await event_store.push_event(run_id, {
                "type": "research_complete",
                "data": {
                    "company_kb_id": str(company_kb_id),
                    "company_name": company_name,
                    "fields_updated": fields_updated,
                    "updated_data": result.get("updated_data", {}),
                    "current_data": result.get("current_data", {}),
                },
            })

    except Exception as e:
        logger.error(f"Company research background task failed: {e}", exc_info=True)
        await event_store.push_event(run_id, {
            "type": "research_failed",
            "data": {"message": "Company research failed. Please try again."},
        })


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

    draft_result = await generate_outreach_draft(
        db, company_kb_id,
        contact_name=request.contact_name,
        contact_title=request.contact_title,
        context=request.context,
        format=request.format,
        tone=request.tone,
        signal_id=request.signal_id,
    )

    draft_text = draft_result["primary"]

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
        "drafts": draft_result.get("drafts", []),
        "template_used": draft_result.get("template_used"),
        "template_hint": draft_result.get("template_hint"),
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
            # Mark the linked signal as acted_on
            if draft.signal_id:
                from app.models.signal_event import SignalEvent
                from sqlalchemy.sql import func as sa_func
                sig_result = await db.execute(
                    select(SignalEvent).where(SignalEvent.id == draft.signal_id)
                )
                signal = sig_result.scalar_one_or_none()
                if signal:
                    signal.is_acted_on = True
                    signal.acted_on_at = sa_func.now()

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


@router.get("/{company_kb_id}/export/pdf")
async def export_brief_pdf(
    company_kb_id: UUID,
    version: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Export a research brief as a PDF document.

    Uses WeasyPrint for PDF generation when available.
    Falls back to returning HTML with an appropriate content type if not.
    """
    from app.services.signal_export_service import generate_brief_html, generate_brief_pdf
    from io import BytesIO

    html = await generate_brief_html(db, company_kb_id, version=version)
    pdf_bytes = generate_brief_pdf(html)

    # Determine if we got a real PDF or an HTML fallback
    is_pdf = pdf_bytes[:5] == b"%PDF-"
    media_type = "application/pdf" if is_pdf else "text/html; charset=utf-8"
    extension = "pdf" if is_pdf else "html"

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="brief_{company_kb_id}.{extension}"',
        },
    )


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
