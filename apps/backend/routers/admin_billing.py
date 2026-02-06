"""Admin billing endpoints: usage, limits, pricing."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from apps.backend.deps import get_db
from apps.backend.auth import get_current_admin
from apps.backend.models.billing import BillingUsage
from apps.backend.services.billing import (
    get_pricing,
    set_pricing,
    get_portal_usage_summary,
    set_portal_limit,
    get_portal_limit,
)

router = APIRouter()


@router.get("/pricing")
def billing_get_pricing(
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return get_pricing(db)


@router.post("/pricing")
def billing_set_pricing(
    chat_rub_per_1k: float | None = Body(None),
    embed_rub_per_1k: float | None = Body(None),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return set_pricing(db, chat_rub_per_1k, embed_rub_per_1k)


@router.get("/portals/{portal_id}/summary")
def billing_portal_summary(
    portal_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return get_portal_usage_summary(db, portal_id)


@router.post("/portals/{portal_id}/limit")
def billing_set_portal_limit(
    portal_id: int,
    monthly_request_limit: int | None = Body(None),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return {"portal_id": portal_id, "monthly_request_limit": set_portal_limit(db, portal_id, monthly_request_limit)}


@router.get("/usage")
def billing_usage_list(
    portal_id: int | None = Query(None),
    user_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    q = select(BillingUsage).order_by(desc(BillingUsage.created_at)).limit(limit)
    if portal_id:
        q = q.where(BillingUsage.portal_id == portal_id)
    if user_id:
        q = q.where(BillingUsage.user_id == user_id)
    items = db.execute(q).scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "portal_id": r.portal_id,
                "user_id": r.user_id,
                "request_id": r.request_id,
                "kind": r.kind,
                "model": r.model,
                "tokens_prompt": r.tokens_prompt,
                "tokens_completion": r.tokens_completion,
                "tokens_total": r.tokens_total,
                "cost_rub": float(r.cost_rub or 0),
                "status": r.status,
                "error_code": r.error_code,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in items
        ]
    }
