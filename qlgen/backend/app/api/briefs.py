"""Account Brief, Outreach Draft & Company Research API endpoints."""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.services.brief_service import generate_brief

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/briefs", tags=["briefs"])


@router.post("/generate/{company_kb_id}")
async def generate_company_brief(
    company_kb_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate an account brief for a company."""
    brief_markdown = await generate_brief(db, company_kb_id)
    return {
        "company_kb_id": str(company_kb_id),
        "brief": brief_markdown,
    }


# ── Outreach Draft ──


class OutreachDraftRequest(BaseModel):
    contact_name: Optional[str] = None
    context: Optional[str] = None


@router.post("/outreach/{company_kb_id}")
async def generate_outreach(
    company_kb_id: UUID,
    request: OutreachDraftRequest = OutreachDraftRequest(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate a curated outreach email draft for a company."""
    from app.services.outreach_service import generate_outreach_draft

    draft = await generate_outreach_draft(
        db, company_kb_id,
        contact_name=request.contact_name,
        context=request.context,
    )
    return {
        "company_kb_id": str(company_kb_id),
        "draft": draft,
    }


# ── Company Research ──


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
