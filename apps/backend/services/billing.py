"""Billing helpers: limits, usage, pricing."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from apps.backend.models.app_setting import AppSetting
from apps.backend.models.billing import PortalUsageLimit, BillingUsage

PRICING_KEY = "gigachat_pricing"


def _month_range(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.utcnow()
    start = datetime(now.year, now.month, 1)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1)
    else:
        end = datetime(now.year, now.month + 1, 1)
    return start, end


def get_pricing(db: Session) -> dict[str, Any]:
    row = db.get(AppSetting, PRICING_KEY)
    if not row:
        return {
            "chat_rub_per_1k": 0.0,
            "embed_rub_per_1k": 0.0,
        }
    data = row.value_json or {}
    return {
        "chat_rub_per_1k": float(data.get("chat_rub_per_1k") or 0.0),
        "embed_rub_per_1k": float(data.get("embed_rub_per_1k") or 0.0),
    }


def set_pricing(db: Session, chat_rub_per_1k: float | None, embed_rub_per_1k: float | None) -> dict[str, Any]:
    row = db.get(AppSetting, PRICING_KEY)
    data = dict(row.value_json or {}) if row else {}
    if chat_rub_per_1k is not None:
        data["chat_rub_per_1k"] = float(chat_rub_per_1k)
    if embed_rub_per_1k is not None:
        data["embed_rub_per_1k"] = float(embed_rub_per_1k)
    if not row:
        row = AppSetting(key=PRICING_KEY, value_json=data)
        db.add(row)
    else:
        row.value_json = dict(data)
    db.commit()
    return get_pricing(db)


def get_portal_limit(db: Session, portal_id: int) -> int | None:
    row = db.get(PortalUsageLimit, portal_id)
    if not row:
        return None
    return row.monthly_request_limit


def set_portal_limit(db: Session, portal_id: int, monthly_request_limit: int | None) -> int | None:
    row = db.get(PortalUsageLimit, portal_id)
    if not row:
        row = PortalUsageLimit(portal_id=portal_id)
        db.add(row)
    row.monthly_request_limit = monthly_request_limit
    row.updated_at = datetime.utcnow()
    db.commit()
    return row.monthly_request_limit


def get_portal_usage_count(db: Session, portal_id: int) -> int:
    start, end = _month_range()
    q = select(func.count(BillingUsage.id)).where(
        BillingUsage.portal_id == portal_id,
        BillingUsage.kind == "chat",
        BillingUsage.status == "ok",
        BillingUsage.created_at >= start,
        BillingUsage.created_at < end,
    )
    return int(db.execute(q).scalar() or 0)


def calc_cost_rub(tokens_total: int | None, rub_per_1k: float) -> Decimal | None:
    if not tokens_total or rub_per_1k <= 0:
        return None
    return Decimal(tokens_total) * Decimal(str(rub_per_1k)) / Decimal(1000)


def record_usage(
    db: Session,
    *,
    portal_id: int,
    user_id: str | None,
    request_id: str | None,
    kind: str,
    model: str | None,
    tokens_prompt: int | None,
    tokens_completion: int | None,
    tokens_total: int | None,
    cost_rub: Decimal | None,
    status: str = "ok",
    error_code: str | None = None,
) -> BillingUsage:
    row = BillingUsage(
        portal_id=portal_id,
        user_id=user_id,
        request_id=request_id,
        kind=kind,
        model=model,
        tokens_prompt=tokens_prompt,
        tokens_completion=tokens_completion,
        tokens_total=tokens_total,
        cost_rub=cost_rub,
        status=status,
        error_code=error_code,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_portal_usage_summary(db: Session, portal_id: int) -> dict[str, Any]:
    start, end = _month_range()
    limit = get_portal_limit(db, portal_id)
    used = get_portal_usage_count(db, portal_id)
    percent = 0
    if limit and limit > 0:
        percent = min(100, int((used / limit) * 100))
    q = select(
        func.coalesce(func.sum(BillingUsage.tokens_total), 0),
        func.coalesce(func.sum(BillingUsage.cost_rub), 0),
    ).where(
        BillingUsage.portal_id == portal_id,
        BillingUsage.created_at >= start,
        BillingUsage.created_at < end,
    )
    tokens_sum, cost_sum = db.execute(q).one()
    return {
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "limit_requests": limit,
        "used_requests": used,
        "percent": percent,
        "tokens_total": int(tokens_sum or 0),
        "cost_rub": float(cost_sum or 0),
    }


def is_limit_exceeded(db: Session, portal_id: int) -> bool:
    limit = get_portal_limit(db, portal_id)
    if not limit or limit <= 0:
        return False
    used = get_portal_usage_count(db, portal_id)
    return used >= limit
