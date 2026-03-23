"""Billing helpers: limits, usage, pricing, and account-level plan policy."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from apps.backend.models.app_setting import AppSetting
from apps.backend.models.account import Account, AccountMembership, AppUserWebCredential
from apps.backend.models.billing import (
    AccountPlanOverride,
    AccountSubscription,
    BillingPlan,
    BillingUsage,
    PortalUsageLimit,
)
from apps.backend.models.kb import KBChunk, KBFile
from apps.backend.models.portal import Portal
from apps.backend.services.activity import log_activity

PRICING_KEY = "gigachat_pricing"

DEFAULT_LIMITS: dict[str, int] = {
    "requests_per_month": 10000,
    "media_minutes_per_month": 300,
    "max_users": 25,
    "max_storage_gb": 50,
}

DEFAULT_FEATURES: dict[str, bool] = {
    "allow_model_selection": True,
    "allow_advanced_model_tuning": False,
    "allow_media_transcription": True,
    "allow_speaker_diarization": False,
    "allow_client_bot": True,
    "allow_bitrix_integration": True,
    "allow_amocrm_integration": False,
    "allow_webhooks": True,
}

BASE_PLANS: list[dict[str, Any]] = [
    {
        "code": "start",
        "name": "Start",
        "price_month": Decimal("4900.00"),
        "currency": "RUB",
        "limits_json": {
            "requests_per_month": 3000,
            "media_minutes_per_month": 60,
            "max_users": 5,
            "max_storage_gb": 10,
        },
        "features_json": {
            "allow_model_selection": False,
            "allow_advanced_model_tuning": False,
            "allow_media_transcription": False,
            "allow_speaker_diarization": False,
            "allow_client_bot": True,
            "allow_bitrix_integration": True,
            "allow_amocrm_integration": False,
            "allow_webhooks": False,
        },
    },
    {
        "code": "business",
        "name": "Business",
        "price_month": Decimal("14900.00"),
        "currency": "RUB",
        "limits_json": dict(DEFAULT_LIMITS),
        "features_json": dict(DEFAULT_FEATURES),
    },
    {
        "code": "pro",
        "name": "Pro",
        "price_month": Decimal("39900.00"),
        "currency": "RUB",
        "limits_json": {
            "requests_per_month": 50000,
            "media_minutes_per_month": 1200,
            "max_users": 200,
            "max_storage_gb": 500,
        },
        "features_json": {
            "allow_model_selection": True,
            "allow_advanced_model_tuning": True,
            "allow_media_transcription": True,
            "allow_speaker_diarization": True,
            "allow_client_bot": True,
            "allow_bitrix_integration": True,
            "allow_amocrm_integration": True,
            "allow_webhooks": True,
        },
    },
]


def _month_range(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.utcnow()
    start = datetime(now.year, now.month, 1)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1)
    else:
        end = datetime(now.year, now.month + 1, 1)
    return start, end


def _plan_payload(plan: BillingPlan) -> dict[str, Any]:
    return {
        "id": plan.id,
        "code": plan.code,
        "name": plan.name,
        "is_active": bool(plan.is_active),
        "price_month": float(plan.price_month or 0),
        "currency": plan.currency or "RUB",
        "limits": dict(plan.limits_json or {}),
        "features": dict(plan.features_json or {}),
    }


def ensure_base_plans(db: Session) -> list[BillingPlan]:
    plans_by_code = {
        row.code: row
        for row in db.execute(select(BillingPlan).where(BillingPlan.code.is_not(None))).scalars().all()
    }
    changed = False
    for spec in BASE_PLANS:
        row = plans_by_code.get(spec["code"])
        if not row:
            row = BillingPlan(code=spec["code"], name=spec["name"])
            db.add(row)
            plans_by_code[spec["code"]] = row
            changed = True
        row.name = spec["name"]
        row.is_active = True
        row.price_month = spec["price_month"]
        row.currency = spec["currency"]
        row.limits_json = dict(spec["limits_json"])
        row.features_json = dict(spec["features_json"])
    if changed:
        db.commit()
    else:
        db.flush()
    return db.execute(select(BillingPlan).order_by(BillingPlan.id.asc())).scalars().all()


def list_billing_plans(db: Session) -> list[dict[str, Any]]:
    ensure_base_plans(db)
    items = db.execute(select(BillingPlan).order_by(BillingPlan.id.asc())).scalars().all()
    return [_plan_payload(item) for item in items]


def list_billing_accounts(db: Session, *, limit: int = 200) -> list[dict[str, Any]]:
    ensure_base_plans(db)
    rows = db.execute(
        select(Account, AppUserWebCredential.email)
        .join(AppUserWebCredential, AppUserWebCredential.user_id == Account.owner_user_id, isouter=True)
        .order_by(Account.account_no.asc().nullslast(), Account.id.asc())
        .limit(limit)
    ).all()
    items: list[dict[str, Any]] = []
    for account, owner_email in rows:
        sub_payload = get_account_subscription_payload(db, int(account.id))
        subscription = sub_payload.get("subscription")
        items.append(
            {
                "id": int(account.id),
                "account_no": int(account.account_no) if account.account_no is not None else None,
                "name": account.name or f"Account #{account.id}",
                "slug": account.slug,
                "status": account.status,
                "owner_email": owner_email,
                "subscription": subscription,
            }
        )
    return items


def get_active_subscription(db: Session, account_id: int) -> AccountSubscription | None:
    q = (
        select(AccountSubscription)
        .where(AccountSubscription.account_id == account_id)
        .where(AccountSubscription.status.in_(["trial", "active", "paused"]))
        .order_by(desc(AccountSubscription.started_at), desc(AccountSubscription.created_at), desc(AccountSubscription.id))
        .limit(1)
    )
    return db.execute(q).scalars().first()


def get_account_subscription_payload(db: Session, account_id: int) -> dict[str, Any]:
    ensure_base_plans(db)
    sub = get_active_subscription(db, account_id)
    if not sub:
        return {
            "account_id": account_id,
            "subscription": None,
        }
    plan = db.get(BillingPlan, sub.plan_id)
    return {
        "account_id": account_id,
        "subscription": {
            "id": sub.id,
            "status": sub.status,
            "trial_until": sub.trial_until.isoformat() if sub.trial_until else None,
            "started_at": sub.started_at.isoformat() if sub.started_at else None,
            "ended_at": sub.ended_at.isoformat() if sub.ended_at else None,
            "plan": _plan_payload(plan) if plan else None,
        },
    }


def _get_active_override(db: Session, account_id: int, now: datetime | None = None) -> AccountPlanOverride | None:
    now = now or datetime.utcnow()
    q = (
        select(AccountPlanOverride)
        .where(AccountPlanOverride.account_id == account_id)
        .where(and_(
            (AccountPlanOverride.valid_from.is_(None) | (AccountPlanOverride.valid_from <= now)),
            (AccountPlanOverride.valid_to.is_(None) | (AccountPlanOverride.valid_to >= now)),
        ))
        .order_by(desc(AccountPlanOverride.created_at), desc(AccountPlanOverride.id))
        .limit(1)
    )
    return db.execute(q).scalars().first()


def get_account_effective_policy(db: Session, account_id: int) -> dict[str, Any]:
    ensure_base_plans(db)
    limits = dict(DEFAULT_LIMITS)
    features = dict(DEFAULT_FEATURES)
    source = "default"
    plan_payload = None

    sub = get_active_subscription(db, account_id)
    if sub:
        plan = db.get(BillingPlan, sub.plan_id)
        if plan:
            limits.update(dict(plan.limits_json or {}))
            features.update(dict(plan.features_json or {}))
            source = "plan"
            plan_payload = _plan_payload(plan)

    override = _get_active_override(db, account_id)
    if override:
        limits.update(dict(override.limits_json or {}))
        features.update(dict(override.features_json or {}))
        source = "override"

    return {
        "account_id": account_id,
        "plan_code": plan_payload.get("code") if plan_payload else "default",
        "plan": plan_payload,
        "limits": limits,
        "features": features,
        "source": source,
        "subscription_status": sub.status if sub else None,
        "override": {
            "id": override.id,
            "reason": override.reason,
            "valid_from": override.valid_from.isoformat() if override and override.valid_from else None,
            "valid_to": override.valid_to.isoformat() if override and override.valid_to else None,
        } if override else None,
    }


def get_portal_effective_policy(db: Session, portal_id: int) -> dict[str, Any]:
    account_id = db.execute(select(Portal.account_id).where(Portal.id == portal_id)).scalar()
    if account_id:
        return get_account_effective_policy(db, int(account_id))
    return {
        "account_id": None,
        "plan_code": "default",
        "plan": None,
        "limits": dict(DEFAULT_LIMITS),
        "features": dict(DEFAULT_FEATURES),
        "source": "default",
        "subscription_status": None,
        "override": None,
    }


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


def _account_portal_ids(db: Session, account_id: int) -> list[int]:
    rows = db.execute(select(Portal.id).where(Portal.account_id == account_id)).all()
    return [int(row[0]) for row in rows if row and row[0] is not None]


def get_account_usage_summary(db: Session, account_id: int) -> dict[str, Any]:
    start, end = _month_range()
    portal_ids = _account_portal_ids(db, account_id)
    policy = get_account_effective_policy(db, account_id)
    limits = dict(policy.get("limits") or {})

    requests_used = 0
    tokens_total = 0
    cost_rub = 0.0
    storage_used_bytes = 0
    media_minutes_used = 0

    if portal_ids:
        q_requests = select(func.count(BillingUsage.id)).where(
            BillingUsage.portal_id.in_(portal_ids),
            BillingUsage.kind == "chat",
            BillingUsage.status == "ok",
            BillingUsage.created_at >= start,
            BillingUsage.created_at < end,
        )
        requests_used = int(db.execute(q_requests).scalar() or 0)
        q_usage = select(
            func.coalesce(func.sum(BillingUsage.tokens_total), 0),
            func.coalesce(func.sum(BillingUsage.cost_rub), 0),
        ).where(
            BillingUsage.portal_id.in_(portal_ids),
            BillingUsage.created_at >= start,
            BillingUsage.created_at < end,
        )
        tokens_total, cost_sum = db.execute(q_usage).one()
        cost_rub = float(cost_sum or 0.0)
        q_storage = select(func.coalesce(func.sum(KBFile.size_bytes), 0)).where(
            KBFile.portal_id.in_(portal_ids),
            KBFile.status != "error",
        )
        storage_used_bytes = int(db.execute(q_storage).scalar() or 0)

        q_media = (
            select(func.max(KBChunk.end_ms))
            .select_from(KBChunk)
            .join(KBFile, KBFile.id == KBChunk.file_id)
            .where(
                KBChunk.portal_id.in_(portal_ids),
                KBFile.created_at >= start,
                KBFile.created_at < end,
                KBChunk.end_ms.is_not(None),
            )
            .group_by(KBChunk.file_id)
        )
        media_rows = db.execute(q_media).scalars().all()
        media_minutes_used = int(sum(float(x or 0.0) for x in media_rows) / 60000.0)

    users_used = int(
        db.execute(
            select(func.count(AccountMembership.id)).where(
                AccountMembership.account_id == account_id,
                AccountMembership.status == "active",
            )
        ).scalar()
        or 0
    )

    storage_used_gb = round(storage_used_bytes / (1024 ** 3), 2) if storage_used_bytes > 0 else 0.0
    usage = {
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "requests_used": int(requests_used or 0),
        "requests_limit": int(limits.get("requests_per_month") or 0),
        "media_minutes_used": int(media_minutes_used or 0),
        "media_minutes_limit": int(limits.get("media_minutes_per_month") or 0),
        "users_used": users_used,
        "users_limit": int(limits.get("max_users") or 0),
        "storage_used_gb": storage_used_gb,
        "storage_limit_gb": int(limits.get("max_storage_gb") or 0),
        "tokens_total": int(tokens_total or 0),
        "cost_rub": cost_rub,
    }
    return usage


def get_account_active_user_count(db: Session, account_id: int) -> int:
    return int(
        db.execute(
            select(func.count(AccountMembership.id)).where(
                AccountMembership.account_id == account_id,
                AccountMembership.status == "active",
            )
        ).scalar()
        or 0
    )


def is_account_user_limit_reached(db: Session, account_id: int, *, extra_users: int = 1) -> bool:
    policy = get_account_effective_policy(db, account_id)
    limit = int((policy.get("limits") or {}).get("max_users") or 0)
    if limit <= 0:
        return False
    used = get_account_active_user_count(db, account_id)
    return (used + max(0, int(extra_users))) > limit


def would_exceed_account_media_minutes(db: Session, account_id: int, *, additional_minutes: int) -> bool:
    policy = get_account_effective_policy(db, account_id)
    limit = int((policy.get("limits") or {}).get("media_minutes_per_month") or 0)
    if limit <= 0:
        return False
    used = int(get_account_usage_summary(db, account_id).get("media_minutes_used") or 0)
    return (used + max(0, int(additional_minutes))) > limit


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
    try:
        log_activity(db, kind="ai", portal_id=portal_id, web_user_id=None)
    except Exception:
        pass
    return row


def get_portal_usage_summary(db: Session, portal_id: int) -> dict[str, Any]:
    start, end = _month_range()
    portal_limit = get_portal_limit(db, portal_id)
    account_id = db.execute(select(Portal.account_id).where(Portal.id == portal_id)).scalar()
    if account_id and not portal_limit:
        account_usage = get_account_usage_summary(db, int(account_id))
        used = int(account_usage.get("requests_used") or 0)
        limit = int(account_usage.get("requests_limit") or 0) or None
    else:
        limit = portal_limit
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
    portal_limit = get_portal_limit(db, portal_id)
    if portal_limit and portal_limit > 0:
        used = get_portal_usage_count(db, portal_id)
        return used >= portal_limit
    account_id = db.execute(select(Portal.account_id).where(Portal.id == portal_id)).scalar()
    if not account_id:
        return False
    usage = get_account_usage_summary(db, int(account_id))
    limit = int(usage.get("requests_limit") or 0)
    if limit <= 0:
        return False
    return int(usage.get("requests_used") or 0) >= limit


def _normalize_limits_payload(payload: dict[str, Any] | None) -> dict[str, int]:
    raw = dict(payload or {})
    unknown = sorted(set(raw) - set(DEFAULT_LIMITS))
    if unknown:
        raise ValueError(f"unknown_limit_keys:{','.join(unknown)}")
    out: dict[str, int] = {}
    for key, value in raw.items():
        try:
            normalized = int(value)
        except Exception as exc:
            raise ValueError(f"invalid_limit_value:{key}") from exc
        if normalized < 0:
            raise ValueError(f"negative_limit_value:{key}")
        out[key] = normalized
    return out


def _normalize_features_payload(payload: dict[str, Any] | None) -> dict[str, bool]:
    raw = dict(payload or {})
    unknown = sorted(set(raw) - set(DEFAULT_FEATURES))
    if unknown:
        raise ValueError(f"unknown_feature_keys:{','.join(unknown)}")
    out: dict[str, bool] = {}
    for key, value in raw.items():
        if isinstance(value, bool):
            out[key] = value
            continue
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes"}:
                out[key] = True
                continue
            if lowered in {"false", "0", "no"}:
                out[key] = False
                continue
        raise ValueError(f"invalid_feature_value:{key}")
    return out


def create_billing_plan(
    db: Session,
    *,
    code: str,
    name: str,
    price_month: float,
    currency: str,
    limits_json: dict[str, Any] | None,
    features_json: dict[str, Any] | None,
    is_active: bool = True,
) -> dict[str, Any]:
    ensure_base_plans(db)
    code = (code or "").strip().lower()
    if not code:
        raise ValueError("code_required")
    if db.execute(select(BillingPlan).where(BillingPlan.code == code)).scalars().first():
        raise ValueError("code_exists")
    row = BillingPlan(
        code=code,
        name=(name or "").strip() or code,
        is_active=bool(is_active),
        price_month=Decimal(str(price_month)),
        currency=(currency or "RUB").strip().upper() or "RUB",
        limits_json=_normalize_limits_payload(limits_json),
        features_json=_normalize_features_payload(features_json),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _plan_payload(row)


def update_billing_plan(
    db: Session,
    *,
    plan_id: int,
    name: str | None = None,
    price_month: float | None = None,
    currency: str | None = None,
    limits_json: dict[str, Any] | None = None,
    features_json: dict[str, Any] | None = None,
    is_active: bool | None = None,
) -> dict[str, Any]:
    ensure_base_plans(db)
    row = db.get(BillingPlan, plan_id)
    if not row:
        raise ValueError("plan_not_found")
    if name is not None:
        row.name = name.strip() or row.name
    if price_month is not None:
        row.price_month = Decimal(str(price_month))
    if currency is not None:
        row.currency = currency.strip().upper() or row.currency
    if limits_json is not None:
        row.limits_json = _normalize_limits_payload(limits_json)
    if features_json is not None:
        row.features_json = _normalize_features_payload(features_json)
    if is_active is not None:
        row.is_active = bool(is_active)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _plan_payload(row)


def set_billing_plan_active(db: Session, *, plan_id: int, is_active: bool) -> dict[str, Any]:
    return update_billing_plan(db, plan_id=plan_id, is_active=is_active)


def upsert_account_subscription(
    db: Session,
    *,
    account_id: int,
    plan_id: int,
    status: str,
    trial_until: datetime | None = None,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
) -> dict[str, Any]:
    ensure_base_plans(db)
    plan = db.get(BillingPlan, plan_id)
    if not plan:
        raise ValueError("plan_not_found")
    if status not in {"trial", "active", "paused", "canceled"}:
        raise ValueError("invalid_subscription_status")
    row = get_active_subscription(db, account_id)
    if row is None:
        row = AccountSubscription(account_id=account_id, plan_id=plan_id)
        db.add(row)
    row.plan_id = plan_id
    row.status = status
    row.trial_until = trial_until
    row.started_at = started_at or row.started_at or datetime.utcnow()
    row.ended_at = ended_at
    row.updated_at = datetime.utcnow()
    db.commit()
    return get_account_subscription_payload(db, account_id)


def list_account_plan_overrides(db: Session, account_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        select(AccountPlanOverride)
        .where(AccountPlanOverride.account_id == account_id)
        .order_by(desc(AccountPlanOverride.created_at), desc(AccountPlanOverride.id))
    ).scalars().all()
    return [
        {
            "id": row.id,
            "account_id": row.account_id,
            "limits": dict(row.limits_json or {}),
            "features": dict(row.features_json or {}),
            "valid_from": row.valid_from.isoformat() if row.valid_from else None,
            "valid_to": row.valid_to.isoformat() if row.valid_to else None,
            "reason": row.reason,
            "created_by": row.created_by,
        }
        for row in rows
    ]


def _validate_override_window(db: Session, *, account_id: int, valid_from: datetime | None, valid_to: datetime | None, exclude_id: int | None = None) -> None:
    rows = db.execute(
        select(AccountPlanOverride)
        .where(AccountPlanOverride.account_id == account_id)
        .order_by(desc(AccountPlanOverride.created_at), desc(AccountPlanOverride.id))
    ).scalars().all()
    for row in rows:
        if exclude_id and row.id == exclude_id:
            continue
        row_from = row.valid_from or datetime.min
        row_to = row.valid_to or datetime.max
        new_from = valid_from or datetime.min
        new_to = valid_to or datetime.max
        if new_from <= row_to and row_from <= new_to:
            raise ValueError("override_window_overlap")


def create_account_plan_override(
    db: Session,
    *,
    account_id: int,
    limits_json: dict[str, Any] | None,
    features_json: dict[str, Any] | None,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    reason: str | None = None,
    created_by: str | None = None,
) -> dict[str, Any]:
    _validate_override_window(db, account_id=account_id, valid_from=valid_from, valid_to=valid_to)
    row = AccountPlanOverride(
        account_id=account_id,
        limits_json=_normalize_limits_payload(limits_json),
        features_json=_normalize_features_payload(features_json),
        valid_from=valid_from,
        valid_to=valid_to,
        reason=(reason or "").strip() or None,
        created_by=(created_by or "").strip() or None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return list_account_plan_overrides(db, account_id)[0]


def update_account_plan_override(
    db: Session,
    *,
    override_id: int,
    limits_json: dict[str, Any] | None = None,
    features_json: dict[str, Any] | None = None,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    row = db.get(AccountPlanOverride, override_id)
    if not row:
        raise ValueError("override_not_found")
    next_valid_from = valid_from if valid_from is not None else row.valid_from
    next_valid_to = valid_to if valid_to is not None else row.valid_to
    _validate_override_window(
        db,
        account_id=row.account_id,
        valid_from=next_valid_from,
        valid_to=next_valid_to,
        exclude_id=row.id,
    )
    if limits_json is not None:
        row.limits_json = _normalize_limits_payload(limits_json)
    if features_json is not None:
        row.features_json = _normalize_features_payload(features_json)
    if valid_from is not None:
        row.valid_from = valid_from
    if valid_to is not None:
        row.valid_to = valid_to
    if reason is not None:
        row.reason = reason.strip() or None
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return list_account_plan_overrides(db, row.account_id)[0]


def delete_account_plan_override(db: Session, *, override_id: int) -> dict[str, Any]:
    row = db.get(AccountPlanOverride, override_id)
    if not row:
        raise ValueError("override_not_found")
    payload = {"deleted": True, "override_id": row.id, "account_id": row.account_id}
    db.delete(row)
    db.commit()
    return payload
