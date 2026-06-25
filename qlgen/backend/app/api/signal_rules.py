"""Custom Signal Rules API endpoints."""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.services.custom_rules_service import (
    create_rule, get_rules_for_user, get_rule, update_rule,
    delete_rule, toggle_rule, evaluate_rules_for_company,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/signal-rules", tags=["signal-rules"])


# ──────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────

class CreateRuleRequest(BaseModel):
    name: str
    description: Optional[str] = None
    rule_type: str  # keyword, pattern, composite
    rule_config: dict
    tracking_list_id: Optional[str] = None
    signal_type_output: str = "custom_signal"
    priority_output: str = "medium"


class UpdateRuleRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rule_config: Optional[dict] = None
    signal_type_output: Optional[str] = None
    priority_output: Optional[str] = None
    is_active: Optional[bool] = None


class EvaluateRequest(BaseModel):
    company_kb_id: str
    search_text: str = ""


def _serialize_rule(rule) -> dict:
    return {
        "id": str(rule.id),
        "user_id": str(rule.user_id),
        "tracking_list_id": str(rule.tracking_list_id) if rule.tracking_list_id else None,
        "name": rule.name,
        "description": rule.description,
        "rule_type": rule.rule_type,
        "rule_config": rule.rule_config,
        "signal_type_output": rule.signal_type_output,
        "priority_output": rule.priority_output,
        "is_active": rule.is_active,
        "last_triggered_at": rule.last_triggered_at.isoformat() if rule.last_triggered_at else None,
        "trigger_count": rule.trigger_count or 0,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


# ──────────────────────────────────────────────────────────────────
# CRUD endpoints
# ──────────────────────────────────────────────────────────────────

@router.get("")
async def list_rules(
    tracking_list_id: Optional[str] = Query(None),
    active_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tl_id = UUID(tracking_list_id) if tracking_list_id else None
    rules = await get_rules_for_user(db, user.id, tracking_list_id=tl_id, active_only=active_only)
    return {
        "rules": [_serialize_rule(r) for r in rules],
        "total": len(rules),
    }


@router.post("")
async def create(
    request: CreateRuleRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if request.rule_type not in ("keyword", "pattern", "composite"):
        raise HTTPException(400, "rule_type must be keyword, pattern, or composite")

    tl_id = UUID(request.tracking_list_id) if request.tracking_list_id else None
    rule = await create_rule(
        db, user.id,
        name=request.name,
        description=request.description,
        rule_type=request.rule_type,
        rule_config=request.rule_config,
        tracking_list_id=tl_id,
        signal_type_output=request.signal_type_output,
        priority_output=request.priority_output,
    )
    await db.commit()
    return _serialize_rule(rule)


@router.get("/{rule_id}")
async def get_one(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rule = await get_rule(db, rule_id)
    if not rule or rule.user_id != user.id:
        raise HTTPException(404, "Rule not found")
    return _serialize_rule(rule)


@router.put("/{rule_id}")
async def update(
    rule_id: UUID,
    request: UpdateRuleRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    existing = await get_rule(db, rule_id)
    if not existing or existing.user_id != user.id:
        raise HTTPException(404, "Rule not found")

    rule = await update_rule(db, rule_id, **request.model_dump(exclude_none=True))
    await db.commit()
    return _serialize_rule(rule)


@router.delete("/{rule_id}")
async def delete(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    existing = await get_rule(db, rule_id)
    if not existing or existing.user_id != user.id:
        raise HTTPException(404, "Rule not found")

    await delete_rule(db, rule_id)
    await db.commit()
    return {"status": "deleted"}


@router.post("/{rule_id}/toggle")
async def toggle(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from sqlalchemy import select as sa_select
    from app.models.custom_signal_rule import CustomSignalRule as CSR
    result = await db.execute(sa_select(CSR).where(CSR.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule or rule.user_id != user.id:
        raise HTTPException(404, "Rule not found")
    rule.is_active = not rule.is_active
    await db.commit()
    await db.refresh(rule)
    return _serialize_rule(rule)


# ──────────────────────────────────────────────────────────────────
# Evaluation
# ──────────────────────────────────────────────────────────────────

@router.post("/evaluate")
async def evaluate(
    request: EvaluateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Test-evaluate all active rules for a company."""
    triggered = await evaluate_rules_for_company(
        db, user.id,
        company_kb_id=UUID(request.company_kb_id),
        search_text=request.search_text,
    )
    await db.commit()
    return {
        "triggered_rules": triggered,
        "total_triggered": len(triggered),
    }
