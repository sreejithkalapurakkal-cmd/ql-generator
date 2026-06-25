"""Custom Signal Sources API endpoints."""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.custom_signal_source import CustomSignalSource, SourceSnapshot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sources", tags=["sources"])


class CreateSourceRequest(BaseModel):
    source_type: str  # website, careers, blog, press, rss
    url: str
    name: Optional[str] = None
    company_kb_id: Optional[str] = None
    crawl_frequency: str = "weekly"
    crawl_config: Optional[dict] = None


class UpdateSourceRequest(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    crawl_frequency: Optional[str] = None
    enabled: Optional[bool] = None
    crawl_config: Optional[dict] = None


def _serialize(s: CustomSignalSource) -> dict:
    return {
        "id": str(s.id),
        "user_id": str(s.user_id),
        "company_kb_id": str(s.company_kb_id) if s.company_kb_id else None,
        "source_type": s.source_type,
        "url": s.url,
        "name": s.name,
        "crawl_frequency": s.crawl_frequency,
        "last_crawled_at": s.last_crawled_at.isoformat() if s.last_crawled_at else None,
        "reliability_score": s.reliability_score,
        "freshness_score": s.freshness_score,
        "enabled": s.enabled,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("")
async def list_sources(
    company_kb_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(CustomSignalSource).where(CustomSignalSource.user_id == user.id)
    if company_kb_id:
        query = query.where(CustomSignalSource.company_kb_id == UUID(company_kb_id))
    query = query.order_by(CustomSignalSource.created_at.desc())
    result = await db.execute(query)
    sources = list(result.scalars().all())
    return {"sources": [_serialize(s) for s in sources], "total": len(sources)}


@router.post("")
async def create_source(
    request: CreateSourceRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if request.source_type not in ("website", "careers", "blog", "press", "rss", "linkedin", "github"):
        raise HTTPException(400, "Invalid source_type")

    source = CustomSignalSource(
        user_id=user.id,
        company_kb_id=UUID(request.company_kb_id) if request.company_kb_id else None,
        source_type=request.source_type,
        url=request.url,
        name=request.name,
        crawl_frequency=request.crawl_frequency,
        crawl_config=request.crawl_config or {},
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return _serialize(source)


@router.put("/{source_id}")
async def update_source(
    source_id: UUID,
    request: UpdateSourceRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CustomSignalSource).where(CustomSignalSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source or source.user_id != user.id:
        raise HTTPException(404, "Source not found")

    for field, value in request.model_dump(exclude_none=True).items():
        setattr(source, field, value)
    await db.commit()
    await db.refresh(source)
    return _serialize(source)


@router.delete("/{source_id}")
async def delete_source(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CustomSignalSource).where(CustomSignalSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source or source.user_id != user.id:
        raise HTTPException(404, "Source not found")
    await db.delete(source)
    await db.commit()
    return {"status": "deleted"}


@router.post("/{source_id}/crawl")
async def crawl_source_now(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Manually trigger a crawl for a source."""
    result = await db.execute(
        select(CustomSignalSource).where(CustomSignalSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source or source.user_id != user.id:
        raise HTTPException(404, "Source not found")

    from app.services.source_connector import crawl_source
    crawl_result = await crawl_source(db, source)
    await db.commit()

    return {
        "source_id": str(source_id),
        "content_hash": crawl_result.content_hash,
        "signals_found": len(crawl_result.extracted_signals),
        "error": crawl_result.error,
    }


@router.get("/{source_id}/snapshots")
async def list_snapshots(
    source_id: UUID,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(SourceSnapshot)
        .where(SourceSnapshot.source_id == source_id)
        .order_by(SourceSnapshot.crawled_at.desc())
        .limit(limit)
    )
    snapshots = list(result.scalars().all())
    return {
        "snapshots": [
            {
                "id": str(s.id),
                "content_hash": s.content_hash,
                "content_summary": s.content_summary,
                "signals_found": len(s.extracted_signals or []),
                "crawled_at": s.crawled_at.isoformat() if s.crawled_at else None,
            }
            for s in snapshots
        ],
    }
