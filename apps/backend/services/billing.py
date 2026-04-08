"""Billing helpers: limits, usage, pricing, and account-level plan policy."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from apps.backend.models.app_setting import AppSetting
from apps.backend.models.account import Account, AccountIntegration, AccountMembership, AppUserWebCredential
from apps.backend.models.billing import (
    BillingAccountAdjustment,
    BillingCohort,
    BillingCohortAssignment,
    BillingCohortPolicy,
    AccountPlanOverride,
    AccountSubscription,
    BillingPlan,
    BillingPlanVersion,
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
    "max_bitrix_portals": 1,
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

ALLOWED_COHORT_RULE_KEYS = {
    "account_created_before",
    "account_created_after",
    "channel",
    "manual_tag",
}

ADJUSTMENT_KINDS_RUNTIME = {"feature_grant", "feature_revoke", "limit_bonus"}
ADJUSTMENT_KINDS_COMMERCIAL = {"discount_percent", "discount_fixed", "custom_price"}
ALL_ADJUSTMENT_KINDS = ADJUSTMENT_KINDS_RUNTIME | ADJUSTMENT_KINDS_COMMERCIAL

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
            "max_bitrix_portals": 1,
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
            "max_bitrix_portals": 5,
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


def _plan_version_payload(version: BillingPlanVersion | None) -> dict[str, Any] | None:
    if not version:
        return None
    return {
        "id": int(version.id),
        "plan_id": int(version.plan_id),
        "version_code": version.version_code,
        "name": version.name,
        "price_month": float(version.price_month or 0),
        "currency": version.currency or "RUB",
        "limits": dict(version.limits_json or {}),
        "features": dict(version.features_json or {}),
        "valid_from": version.valid_from.isoformat() if version.valid_from else None,
        "valid_to": version.valid_to.isoformat() if version.valid_to else None,
        "is_active": bool(version.is_active),
        "is_default_for_new_accounts": bool(version.is_default_for_new_accounts),
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


def list_billing_plans_v2(db: Session) -> list[dict[str, Any]]:
    ensure_base_plans(db)
    items = db.execute(select(BillingPlan).order_by(BillingPlan.id.asc())).scalars().all()
    out: list[dict[str, Any]] = []
    for item in items:
        default_version = db.execute(
            select(BillingPlanVersion)
            .where(BillingPlanVersion.plan_id == item.id)
            .where(BillingPlanVersion.is_active.is_(True))
            .order_by(desc(BillingPlanVersion.is_default_for_new_accounts), desc(BillingPlanVersion.id))
            .limit(1)
        ).scalars().first()
        version_count = int(
            db.execute(select(func.count(BillingPlanVersion.id)).where(BillingPlanVersion.plan_id == item.id)).scalar() or 0
        )
        payload = _plan_payload(item)
        payload["default_version"] = _plan_version_payload(default_version)
        payload["versions_count"] = version_count
        out.append(payload)
    return out


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


def list_revenue_accounts_v2(db: Session, *, limit: int = 200) -> list[dict[str, Any]]:
    ensure_base_plans(db)
    rows = db.execute(
        select(Account, AppUserWebCredential.email)
        .join(AppUserWebCredential, AppUserWebCredential.user_id == Account.owner_user_id, isouter=True)
        .order_by(Account.account_no.asc().nullslast(), Account.id.asc())
        .limit(limit)
    ).all()
    items: list[dict[str, Any]] = []
    for account, owner_email in rows:
        runtime = get_account_effective_runtime_policy_v2(db, int(account.id))
        commercial = get_account_effective_commercial_policy_v2(db, int(account.id))
        active_cohorts = resolve_account_active_cohorts(db, int(account.id))
        adjustments = resolve_account_active_adjustments(db, int(account.id))
        items.append(
            {
                "id": int(account.id),
                "account_no": int(account.account_no) if account.account_no is not None else None,
                "name": account.name or f"Account #{account.id}",
                "slug": account.slug,
                "status": account.status,
                "owner_email": owner_email,
                "plan": commercial.get("plan"),
                "plan_version": commercial.get("plan_version"),
                "subscription_status": commercial.get("subscription_status"),
                "cohorts": [
                    {
                        "id": int(item["cohort"].id),
                        "code": item["cohort"].code,
                        "name": item["cohort"].name,
                        "source": item["source"],
                    }
                    for item in active_cohorts
                ],
                "final_price_month": commercial.get("final_price_month"),
                "currency": commercial.get("currency"),
                "adjustments_count": len(adjustments),
                "runtime_source": runtime.get("source"),
            }
        )
    return items


def get_account_revenue_detail_v2(db: Session, account_id: int) -> dict[str, Any]:
    account = db.get(Account, account_id)
    if not account:
        raise ValueError("account_not_found")
    subscription_payload = get_account_subscription_payload(db, account_id).get("subscription")
    runtime = get_account_effective_runtime_policy_v2(db, account_id)
    commercial = get_account_effective_commercial_policy_v2(db, account_id)
    cohorts = resolve_account_active_cohorts(db, account_id)
    adjustments = resolve_account_active_adjustments(db, account_id)
    return {
        "account": {
            "id": int(account.id),
            "account_no": int(account.account_no) if account.account_no is not None else None,
            "name": account.name,
            "slug": account.slug,
            "status": account.status,
        },
        "subscription": subscription_payload,
        "runtime_policy": runtime,
        "commercial_policy": commercial,
        "cohorts": [
            {
                "id": int(item["cohort"].id),
                "code": item["cohort"].code,
                "name": item["cohort"].name,
                "source": item["source"],
                "policies": [
                    {
                        "id": int(policy.id),
                        "discount_type": policy.discount_type,
                        "discount_value": float(policy.discount_value or 0),
                        "plan_version_id": int(policy.plan_version_id),
                    }
                    for policy in item["policies"]
                ],
            }
            for item in cohorts
        ],
        "adjustments": [
            {
                "id": int(item.id),
                "kind": item.kind,
                "target_key": item.target_key,
                "value_json": dict(item.value_json or {}),
                "valid_from": item.valid_from.isoformat() if item.valid_from else None,
                "valid_to": item.valid_to.isoformat() if item.valid_to else None,
                "reason": item.reason,
            }
            for item in adjustments
        ],
        "usage": get_account_usage_summary(db, account_id),
    }


def _account_adjustment_payload(row: BillingAccountAdjustment | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": int(row.id),
        "account_id": int(row.account_id),
        "kind": row.kind,
        "target_key": row.target_key,
        "value_json": dict(row.value_json or {}),
        "valid_from": row.valid_from.isoformat() if row.valid_from else None,
        "valid_to": row.valid_to.isoformat() if row.valid_to else None,
        "reason": row.reason,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_account_adjustments_v2(db: Session, account_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        select(BillingAccountAdjustment)
        .where(BillingAccountAdjustment.account_id == account_id)
        .order_by(desc(BillingAccountAdjustment.created_at), desc(BillingAccountAdjustment.id))
    ).scalars().all()
    return [_account_adjustment_payload(row) for row in rows if row]


def _validate_adjustment_kind(kind: str) -> str:
    normalized = (kind or "").strip().lower()
    if normalized not in ALL_ADJUSTMENT_KINDS:
        raise ValueError("invalid_adjustment_kind")
    return normalized


def _normalize_adjustment_value(kind: str, target_key: str | None, value_json: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(value_json or {})
    if kind in {"discount_percent", "discount_fixed", "custom_price"}:
        raw = payload.get("value")
        try:
            value = float(raw)
        except Exception as exc:
            raise ValueError("adjustment_value_required") from exc
        if value < 0:
            raise ValueError("adjustment_value_negative")
        return {"value": value}
    if kind == "limit_bonus":
        key = (target_key or "").strip()
        if key not in DEFAULT_LIMITS:
            raise ValueError("invalid_limit_key")
        raw = payload.get("delta", payload.get("value"))
        try:
            value = int(raw)
        except Exception as exc:
            raise ValueError("adjustment_delta_required") from exc
        return {"delta": value}
    if kind in {"feature_grant", "feature_revoke"}:
        key = (target_key or "").strip()
        if key not in DEFAULT_FEATURES:
            raise ValueError("invalid_feature_key")
        return {"enabled": kind == "feature_grant"}
    return payload


def create_account_adjustment_v2(
    db: Session,
    *,
    account_id: int,
    kind: str,
    target_key: str | None = None,
    value_json: dict[str, Any] | None = None,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    reason: str | None = None,
    created_by: str | None = None,
) -> dict[str, Any]:
    account = db.get(Account, account_id)
    if not account:
        raise ValueError("account_not_found")
    normalized_kind = _validate_adjustment_kind(kind)
    row = BillingAccountAdjustment(
        account_id=account_id,
        kind=normalized_kind,
        target_key=(target_key or "").strip() or None,
        value_json=_normalize_adjustment_value(normalized_kind, target_key, value_json),
        valid_from=valid_from,
        valid_to=valid_to,
        reason=(reason or "").strip() or None,
        created_by=(created_by or "").strip() or None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _account_adjustment_payload(row)


def update_account_adjustment_v2(
    db: Session,
    *,
    adjustment_id: int,
    target_key: str | None = None,
    value_json: dict[str, Any] | None = None,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    row = db.get(BillingAccountAdjustment, adjustment_id)
    if not row:
        raise ValueError("adjustment_not_found")
    next_target_key = target_key if target_key is not None else row.target_key
    next_value_json = value_json if value_json is not None else dict(row.value_json or {})
    row.target_key = (next_target_key or "").strip() or None
    row.value_json = _normalize_adjustment_value(row.kind, row.target_key, next_value_json)
    if valid_from is not None:
        row.valid_from = valid_from
    if valid_to is not None:
        row.valid_to = valid_to
    if reason is not None:
        row.reason = reason.strip() or None
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _account_adjustment_payload(row)


def delete_account_adjustment_v2(db: Session, *, adjustment_id: int) -> dict[str, Any]:
    row = db.get(BillingAccountAdjustment, adjustment_id)
    if not row:
        raise ValueError("adjustment_not_found")
    payload = {"deleted": True, "adjustment_id": int(row.id), "account_id": int(row.account_id)}
    db.delete(row)
    db.commit()
    return payload


def _cohort_policy_payload(row: BillingCohortPolicy | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": int(row.id),
        "cohort_id": int(row.cohort_id),
        "plan_version_id": int(row.plan_version_id),
        "discount_type": row.discount_type,
        "discount_value": float(row.discount_value or 0),
        "feature_adjustments_json": dict(row.feature_adjustments_json or {}),
        "limit_adjustments_json": dict(row.limit_adjustments_json or {}),
        "valid_from": row.valid_from.isoformat() if row.valid_from else None,
        "valid_to": row.valid_to.isoformat() if row.valid_to else None,
        "is_active": bool(row.is_active),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _cohort_payload(db: Session, row: BillingCohort | None) -> dict[str, Any] | None:
    if row is None:
        return None
    policies = db.execute(
        select(BillingCohortPolicy)
        .where(BillingCohortPolicy.cohort_id == row.id)
        .order_by(desc(BillingCohortPolicy.created_at), desc(BillingCohortPolicy.id))
    ).scalars().all()
    active_policies = [item for item in policies if _is_active_window(item.valid_from, item.valid_to)]
    account_count = int(
        db.execute(
            select(func.count(BillingCohortAssignment.id)).where(BillingCohortAssignment.cohort_id == row.id)
        ).scalar()
        or 0
    )
    return {
        "id": int(row.id),
        "code": row.code,
        "name": row.name,
        "description": row.description,
        "rule_json": dict(row.rule_json or {}),
        "is_active": bool(row.is_active),
        "accounts_count": account_count,
        "policies": [_cohort_policy_payload(item) for item in active_policies],
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_revenue_cohorts_v2(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(select(BillingCohort).order_by(BillingCohort.id.asc())).scalars().all()
    return [_cohort_payload(db, row) for row in rows if row]


def _normalize_cohort_rule(rule_json: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(rule_json or {})
    unknown = sorted(set(payload) - ALLOWED_COHORT_RULE_KEYS)
    if unknown:
        raise ValueError("invalid_cohort_rule_keys")
    normalized: dict[str, Any] = {}
    if "account_created_before" in payload:
        normalized["account_created_before"] = str(payload["account_created_before"])
    if "account_created_after" in payload:
        normalized["account_created_after"] = str(payload["account_created_after"])
    if "channel" in payload:
        normalized["channel"] = str(payload["channel"]).strip().lower()
    if "manual_tag" in payload:
        normalized["manual_tag"] = str(payload["manual_tag"]).strip()
    return normalized


def create_revenue_cohort_v2(
    db: Session,
    *,
    code: str,
    name: str,
    description: str | None = None,
    rule_json: dict[str, Any] | None = None,
    is_active: bool = True,
) -> dict[str, Any]:
    normalized_code = (code or "").strip().lower()
    if not normalized_code:
        raise ValueError("cohort_code_required")
    if db.execute(select(BillingCohort).where(BillingCohort.code == normalized_code)).scalars().first():
        raise ValueError("cohort_code_exists")
    row = BillingCohort(
        code=normalized_code,
        name=(name or "").strip() or normalized_code,
        description=(description or "").strip() or None,
        rule_json=_normalize_cohort_rule(rule_json),
        is_active=bool(is_active),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _cohort_payload(db, row)


def update_revenue_cohort_v2(
    db: Session,
    *,
    cohort_id: int,
    name: str | None = None,
    description: str | None = None,
    rule_json: dict[str, Any] | None = None,
    is_active: bool | None = None,
) -> dict[str, Any]:
    row = db.get(BillingCohort, cohort_id)
    if not row:
        raise ValueError("cohort_not_found")
    if name is not None:
        row.name = name.strip() or row.name
    if description is not None:
        row.description = description.strip() or None
    if rule_json is not None:
        row.rule_json = _normalize_cohort_rule(rule_json)
    if is_active is not None:
        row.is_active = bool(is_active)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _cohort_payload(db, row)


def list_revenue_cohort_accounts_v2(db: Session, cohort_id: int, *, limit: int = 200) -> list[dict[str, Any]]:
    cohort = db.get(BillingCohort, cohort_id)
    if not cohort:
        raise ValueError("cohort_not_found")
    rows = db.execute(select(Account).order_by(Account.account_no.asc().nullslast(), Account.id.asc())).scalars().all()
    items: list[dict[str, Any]] = []
    manual_assignments = db.execute(
        select(BillingCohortAssignment).where(BillingCohortAssignment.cohort_id == cohort_id)
    ).scalars().all()
    manual_ids = {int(item.account_id) for item in manual_assignments}
    for account in rows:
        source = None
        if int(account.id) in manual_ids:
            source = "manual"
        elif cohort.is_active and _match_cohort_rule(db, account, cohort):
            source = "auto"
        if not source:
            continue
        items.append(
            {
                "id": int(account.id),
                "account_no": int(account.account_no) if account.account_no is not None else None,
                "name": account.name or f"Account #{account.id}",
                "slug": account.slug,
                "status": account.status,
                "source": source,
            }
        )
        if len(items) >= limit:
            break
    return items


def upsert_revenue_cohort_policy_v2(
    db: Session,
    *,
    cohort_id: int,
    plan_version_id: int,
    discount_type: str | None = None,
    discount_value: float | None = None,
    feature_adjustments_json: dict[str, Any] | None = None,
    limit_adjustments_json: dict[str, Any] | None = None,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    is_active: bool = True,
) -> dict[str, Any]:
    cohort = db.get(BillingCohort, cohort_id)
    if not cohort:
        raise ValueError("cohort_not_found")
    version = db.get(BillingPlanVersion, plan_version_id)
    if not version:
        raise ValueError("plan_version_not_found")
    dtype = (discount_type or "none").strip().lower()
    if dtype not in {"none", "percent", "fixed"}:
        raise ValueError("invalid_discount_type")
    dvalue = float(discount_value or 0)
    if dvalue < 0:
        raise ValueError("discount_value_negative")
    row = db.execute(
        select(BillingCohortPolicy)
        .where(BillingCohortPolicy.cohort_id == cohort_id)
        .order_by(desc(BillingCohortPolicy.created_at), desc(BillingCohortPolicy.id))
        .limit(1)
    ).scalars().first()
    if row is None:
        row = BillingCohortPolicy(cohort_id=cohort_id, plan_version_id=plan_version_id)
        db.add(row)
    row.plan_version_id = plan_version_id
    row.discount_type = dtype
    row.discount_value = Decimal(str(dvalue))
    row.feature_adjustments_json = _normalize_features_payload(feature_adjustments_json)
    row.limit_adjustments_json = _normalize_limits_payload(limit_adjustments_json)
    row.valid_from = valid_from
    row.valid_to = valid_to
    row.is_active = bool(is_active)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _cohort_policy_payload(row)


def assign_account_to_cohort_v2(
    db: Session,
    *,
    cohort_id: int,
    account_id: int,
    reason: str | None = None,
    created_by: str | None = None,
) -> dict[str, Any]:
    cohort = db.get(BillingCohort, cohort_id)
    account = db.get(Account, account_id)
    if not cohort:
        raise ValueError("cohort_not_found")
    if not account:
        raise ValueError("account_not_found")
    existing = db.execute(
        select(BillingCohortAssignment)
        .where(BillingCohortAssignment.cohort_id == cohort_id)
        .where(BillingCohortAssignment.account_id == account_id)
        .limit(1)
    ).scalars().first()
    if existing:
        return {
            "id": int(existing.id),
            "cohort_id": int(existing.cohort_id),
            "account_id": int(existing.account_id),
            "source": existing.source,
            "reason": existing.reason,
        }
    row = BillingCohortAssignment(
        cohort_id=cohort_id,
        account_id=account_id,
        source="manual",
        reason=(reason or "").strip() or None,
        created_by=(created_by or "").strip() or None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": int(row.id),
        "cohort_id": int(row.cohort_id),
        "account_id": int(row.account_id),
        "source": row.source,
        "reason": row.reason,
    }


def unassign_account_from_cohort_v2(db: Session, *, cohort_id: int, account_id: int) -> dict[str, Any]:
    row = db.execute(
        select(BillingCohortAssignment)
        .where(BillingCohortAssignment.cohort_id == cohort_id)
        .where(BillingCohortAssignment.account_id == account_id)
        .limit(1)
    ).scalars().first()
    if not row:
        raise ValueError("cohort_assignment_not_found")
    payload = {"deleted": True, "cohort_id": int(cohort_id), "account_id": int(account_id)}
    db.delete(row)
    db.commit()
    return payload


def get_active_subscription(db: Session, account_id: int) -> AccountSubscription | None:
    q = (
        select(AccountSubscription)
        .where(AccountSubscription.account_id == account_id)
        .where(AccountSubscription.status.in_(["trial", "active", "paused"]))
        .order_by(desc(AccountSubscription.started_at), desc(AccountSubscription.created_at), desc(AccountSubscription.id))
        .limit(1)
    )
    return db.execute(q).scalars().first()


def _get_subscription_plan_version(db: Session, sub: AccountSubscription | None) -> BillingPlanVersion | None:
    if not sub:
        return None
    if sub.plan_version_id:
        version = db.get(BillingPlanVersion, int(sub.plan_version_id))
        if version:
            return version
    if not sub.plan_id:
        return None
    return db.execute(
        select(BillingPlanVersion)
        .where(BillingPlanVersion.plan_id == sub.plan_id)
        .where(BillingPlanVersion.is_active.is_(True))
        .order_by(desc(BillingPlanVersion.is_default_for_new_accounts), desc(BillingPlanVersion.id))
        .limit(1)
    ).scalars().first()


def resolve_account_plan_version(db: Session, account_id: int) -> dict[str, Any]:
    ensure_base_plans(db)
    sub = get_active_subscription(db, account_id)
    plan = db.get(BillingPlan, int(sub.plan_id)) if sub and sub.plan_id else None
    version = _get_subscription_plan_version(db, sub)
    return {
        "account_id": int(account_id),
        "subscription": sub,
        "subscription_status": sub.status if sub else None,
        "plan": plan,
        "plan_version": version,
        "plan_payload": _plan_payload(plan) if plan else None,
        "plan_version_payload": _plan_version_payload(version),
    }


def get_account_subscription_payload(db: Session, account_id: int) -> dict[str, Any]:
    ensure_base_plans(db)
    sub = get_active_subscription(db, account_id)
    if not sub:
        return {
            "account_id": account_id,
            "subscription": None,
        }
    plan = db.get(BillingPlan, sub.plan_id)
    version = _get_subscription_plan_version(db, sub)
    return {
        "account_id": account_id,
        "subscription": {
            "id": sub.id,
            "status": sub.status,
            "billing_cycle": getattr(sub, "billing_cycle", "monthly"),
            "trial_until": sub.trial_until.isoformat() if sub.trial_until else None,
            "started_at": sub.started_at.isoformat() if sub.started_at else None,
            "ended_at": sub.ended_at.isoformat() if sub.ended_at else None,
            "plan": _plan_payload(plan) if plan else None,
            "plan_version": _plan_version_payload(version),
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


def _is_active_window(valid_from: datetime | None, valid_to: datetime | None, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    if valid_from and valid_from > now:
        return False
    if valid_to and valid_to < now:
        return False
    return True


def _resolve_account_channel(db: Session, account_id: int) -> str | None:
    provider = db.execute(
        select(AccountIntegration.provider)
        .where(AccountIntegration.account_id == account_id)
        .where(AccountIntegration.status != "deleted")
        .order_by(AccountIntegration.id.asc())
        .limit(1)
    ).scalar()
    return str(provider) if provider else None


def _match_cohort_rule(db: Session, account: Account | None, cohort: BillingCohort) -> bool:
    if not account:
        return False
    rule = dict(cohort.rule_json or {})
    unknown = sorted(set(rule) - ALLOWED_COHORT_RULE_KEYS)
    if unknown:
        return False
    created_at = getattr(account, "created_at", None)
    if "account_created_before" in rule:
        if created_at is None:
            return False
        if created_at >= datetime.fromisoformat(str(rule["account_created_before"]).replace("Z", "+00:00")).replace(tzinfo=None):
            return False
    if "account_created_after" in rule:
        if created_at is None:
            return False
        if created_at <= datetime.fromisoformat(str(rule["account_created_after"]).replace("Z", "+00:00")).replace(tzinfo=None):
            return False
    if "channel" in rule:
        channel = _resolve_account_channel(db, int(account.id))
        if channel != str(rule["channel"]):
            return False
    if "manual_tag" in rule:
        return False
    return True


def resolve_account_active_cohorts(db: Session, account_id: int, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.utcnow()
    account = db.get(Account, account_id)
    if not account:
        return []

    cohorts = db.execute(
        select(BillingCohort).where(BillingCohort.is_active.is_(True)).order_by(BillingCohort.id.asc())
    ).scalars().all()
    manual_assignments = db.execute(
        select(BillingCohortAssignment)
        .where(BillingCohortAssignment.account_id == account_id)
        .order_by(desc(BillingCohortAssignment.id))
    ).scalars().all()
    manual_by_cohort = {int(item.cohort_id): item for item in manual_assignments}
    out: list[dict[str, Any]] = []
    for cohort in cohorts:
        assignment = manual_by_cohort.get(int(cohort.id))
        matched = assignment is not None or _match_cohort_rule(db, account, cohort)
        if not matched:
            continue
        policies = db.execute(
            select(BillingCohortPolicy)
            .where(BillingCohortPolicy.cohort_id == cohort.id)
            .where(BillingCohortPolicy.is_active.is_(True))
            .order_by(desc(BillingCohortPolicy.created_at), desc(BillingCohortPolicy.id))
        ).scalars().all()
        active_policies = [row for row in policies if _is_active_window(row.valid_from, row.valid_to, now)]
        out.append(
            {
                "cohort": cohort,
                "assignment": assignment,
                "policies": active_policies,
                "source": "manual" if assignment is not None else "auto",
            }
        )
    return out


def resolve_account_active_adjustments(db: Session, account_id: int, now: datetime | None = None) -> list[BillingAccountAdjustment]:
    now = now or datetime.utcnow()
    rows = db.execute(
        select(BillingAccountAdjustment)
        .where(BillingAccountAdjustment.account_id == account_id)
        .order_by(desc(BillingAccountAdjustment.created_at), desc(BillingAccountAdjustment.id))
    ).scalars().all()
    return [row for row in rows if _is_active_window(row.valid_from, row.valid_to, now)]


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


def _merge_runtime_limits(base: dict[str, int], patch: dict[str, Any] | None) -> dict[str, int]:
    result = dict(base)
    for key, value in _normalize_limits_payload(patch).items():
        result[key] = value
    return result


def _merge_runtime_features(base: dict[str, bool], patch: dict[str, Any] | None) -> dict[str, bool]:
    result = dict(base)
    for key, value in _normalize_features_payload(patch).items():
        result[key] = value
    return result


def get_account_effective_runtime_policy_v2(db: Session, account_id: int, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.utcnow()
    resolved = resolve_account_plan_version(db, account_id)
    plan = resolved.get("plan")
    version = resolved.get("plan_version")
    sub = resolved.get("subscription")

    limits = dict(DEFAULT_LIMITS)
    features = dict(DEFAULT_FEATURES)
    explain: list[dict[str, Any]] = []

    if version:
        limits = _merge_runtime_limits(limits, version.limits_json or {})
        features = _merge_runtime_features(features, version.features_json or {})
        explain.append(
            {
                "layer": "plan_version",
                "ref": version.version_code,
                "plan_code": plan.code if plan else None,
            }
        )
    elif plan:
        limits = _merge_runtime_limits(limits, plan.limits_json or {})
        features = _merge_runtime_features(features, plan.features_json or {})
        explain.append(
            {
                "layer": "legacy_plan",
                "ref": plan.code,
            }
        )

    active_cohorts = resolve_account_active_cohorts(db, account_id, now=now)
    active_cohort_policies = [policy for item in active_cohorts for policy in item["policies"]]
    if len(active_cohort_policies) > 1:
        raise ValueError("multiple_active_cohort_policies")
    if active_cohort_policies:
        policy = active_cohort_policies[0]
        limits = _merge_runtime_limits(limits, policy.limit_adjustments_json or {})
        features = _merge_runtime_features(features, policy.feature_adjustments_json or {})
        explain.append(
            {
                "layer": "cohort_policy",
                "ref": int(policy.id),
                "cohort_id": int(policy.cohort_id),
            }
        )

    legacy_override = _get_active_override(db, account_id, now=now)
    if legacy_override:
        limits = _merge_runtime_limits(limits, legacy_override.limits_json or {})
        features = _merge_runtime_features(features, legacy_override.features_json or {})
        explain.append(
            {
                "layer": "legacy_override",
                "ref": int(legacy_override.id),
            }
        )

    adjustments = resolve_account_active_adjustments(db, account_id, now=now)
    for item in adjustments:
        if item.kind not in ADJUSTMENT_KINDS_RUNTIME:
            continue
        payload = dict(item.value_json or {})
        if item.kind == "feature_grant" and item.target_key:
            features[item.target_key] = bool(payload.get("enabled", True))
        elif item.kind == "feature_revoke" and item.target_key:
            features[item.target_key] = False if "enabled" not in payload else bool(payload.get("enabled"))
        elif item.kind == "limit_bonus" and item.target_key:
            delta = int(payload.get("delta") or 0)
            limits[item.target_key] = max(0, int(limits.get(item.target_key) or 0) + delta)
        explain.append(
            {
                "layer": "account_adjustment",
                "ref": int(item.id),
                "kind": item.kind,
                "target_key": item.target_key,
            }
        )

    return {
        "account_id": int(account_id),
        "plan_code": plan.code if plan else "default",
        "plan": _plan_payload(plan) if plan else None,
        "plan_version": _plan_version_payload(version),
        "subscription_status": sub.status if sub else None,
        "limits": limits,
        "features": features,
        "source": explain[-1]["layer"] if explain else "default",
        "override": {
            "id": legacy_override.id,
            "reason": legacy_override.reason,
            "valid_from": legacy_override.valid_from.isoformat() if legacy_override.valid_from else None,
            "valid_to": legacy_override.valid_to.isoformat() if legacy_override.valid_to else None,
        } if legacy_override else None,
        "explain": explain,
    }


def get_account_effective_commercial_policy_v2(db: Session, account_id: int, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.utcnow()
    resolved = resolve_account_plan_version(db, account_id)
    plan = resolved.get("plan")
    version = resolved.get("plan_version")
    sub = resolved.get("subscription")

    if version:
        base_price = Decimal(str(version.price_month or 0))
        currency = version.currency or "RUB"
        version_code = version.version_code
    elif plan:
        base_price = Decimal(str(plan.price_month or 0))
        currency = plan.currency or "RUB"
        version_code = None
    else:
        base_price = Decimal("0")
        currency = "RUB"
        version_code = None

    discounts: list[dict[str, Any]] = []
    explain: list[dict[str, Any]] = []
    if version:
        explain.append({"layer": "plan_version", "ref": version.version_code})
    elif plan:
        explain.append({"layer": "legacy_plan", "ref": plan.code})

    final_price = base_price

    active_cohorts = resolve_account_active_cohorts(db, account_id, now=now)
    active_cohort_policies = [policy for item in active_cohorts for policy in item["policies"]]
    if len(active_cohort_policies) > 1:
        raise ValueError("multiple_active_cohort_policies")
    if active_cohort_policies:
        policy = active_cohort_policies[0]
        dtype = (policy.discount_type or "none").strip().lower()
        dvalue = Decimal(str(policy.discount_value or 0))
        if dtype == "percent" and dvalue > 0:
            final_price = final_price * (Decimal("100") - dvalue) / Decimal("100")
            discounts.append({"source": "cohort", "type": "percent", "value": float(dvalue), "ref": int(policy.id)})
        elif dtype == "fixed" and dvalue > 0:
            final_price = final_price - dvalue
            discounts.append({"source": "cohort", "type": "fixed", "value": float(dvalue), "ref": int(policy.id)})
        explain.append({"layer": "cohort_policy", "ref": int(policy.id), "discount_type": dtype})

    adjustments = resolve_account_active_adjustments(db, account_id, now=now)
    custom_price_applied = None
    for item in adjustments:
        if item.kind not in ADJUSTMENT_KINDS_COMMERCIAL:
            continue
        payload = dict(item.value_json or {})
        if item.kind == "discount_percent":
            percent = Decimal(str(payload.get("percent") or 0))
            if percent > 0:
                final_price = final_price * (Decimal("100") - percent) / Decimal("100")
                discounts.append({"source": "account", "type": "percent", "value": float(percent), "ref": int(item.id)})
        elif item.kind == "discount_fixed":
            amount = Decimal(str(payload.get("amount") or 0))
            if amount > 0:
                final_price = final_price - amount
                discounts.append({"source": "account", "type": "fixed", "value": float(amount), "ref": int(item.id)})
        elif item.kind == "custom_price":
            amount = Decimal(str(payload.get("price_month") or 0))
            custom_price_applied = amount
        explain.append({"layer": "account_adjustment", "ref": int(item.id), "kind": item.kind})

    if custom_price_applied is not None:
        final_price = custom_price_applied
        discounts.append({"source": "account", "type": "custom_price", "value": float(custom_price_applied), "ref": "custom"})

    if final_price < 0:
        raise ValueError("negative_final_price")

    return {
        "account_id": int(account_id),
        "plan_code": plan.code if plan else "default",
        "plan": _plan_payload(plan) if plan else None,
        "plan_version": _plan_version_payload(version),
        "plan_version_code": version_code,
        "subscription_status": sub.status if sub else None,
        "base_price_month": float(base_price),
        "currency": currency,
        "discounts": discounts,
        "final_price_month": float(final_price),
        "explain": explain,
    }


def get_portal_effective_policy_v2(db: Session, portal_id: int, now: datetime | None = None) -> dict[str, Any]:
    account_id = db.execute(select(Portal.account_id).where(Portal.id == portal_id)).scalar()
    if account_id:
        return get_account_effective_runtime_policy_v2(db, int(account_id), now=now)
    return {
        "account_id": None,
        "plan_code": "default",
        "plan": None,
        "plan_version": None,
        "limits": dict(DEFAULT_LIMITS),
        "features": dict(DEFAULT_FEATURES),
        "source": "default",
        "subscription_status": None,
        "override": None,
        "explain": [],
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
        "bitrix_portals_used": get_account_bitrix_portal_count(db, account_id),
        "bitrix_portals_limit": int(limits.get("max_bitrix_portals") or 0),
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


def get_account_bitrix_portal_count(db: Session, account_id: int) -> int:
    return int(
        db.execute(
            select(func.count(AccountIntegration.id)).where(
                AccountIntegration.account_id == account_id,
                AccountIntegration.provider == "bitrix",
                AccountIntegration.status != "deleted",
            )
        ).scalar()
        or 0
    )


def is_account_bitrix_portal_limit_reached(db: Session, account_id: int, *, extra_portals: int = 1) -> bool:
    policy = get_account_effective_policy(db, account_id)
    limit = int((policy.get("limits") or {}).get("max_bitrix_portals") or 0)
    if limit <= 0:
        return False
    used = get_account_bitrix_portal_count(db, account_id)
    return (used + max(0, int(extra_portals))) > limit


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


def list_billing_plan_versions(db: Session, plan_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        select(BillingPlanVersion)
        .where(BillingPlanVersion.plan_id == plan_id)
        .order_by(desc(BillingPlanVersion.is_default_for_new_accounts), desc(BillingPlanVersion.id))
    ).scalars().all()
    return [_plan_version_payload(row) for row in rows if row]


def _clear_default_versions(db: Session, plan_id: int, *, exclude_version_id: int | None = None) -> None:
    rows = db.execute(
        select(BillingPlanVersion)
        .where(BillingPlanVersion.plan_id == plan_id)
        .where(BillingPlanVersion.is_default_for_new_accounts.is_(True))
    ).scalars().all()
    for row in rows:
        if exclude_version_id and int(row.id) == int(exclude_version_id):
            continue
        row.is_default_for_new_accounts = False


def create_billing_plan_version(
    db: Session,
    *,
    plan_id: int,
    version_code: str,
    name: str,
    price_month: float,
    currency: str,
    limits_json: dict[str, Any] | None,
    features_json: dict[str, Any] | None,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    is_active: bool = True,
    is_default_for_new_accounts: bool = False,
) -> dict[str, Any]:
    plan = db.get(BillingPlan, plan_id)
    if not plan:
        raise ValueError("plan_not_found")
    code = (version_code or "").strip().lower()
    if not code:
        raise ValueError("version_code_required")
    if db.execute(select(BillingPlanVersion).where(BillingPlanVersion.version_code == code)).scalars().first():
        raise ValueError("version_code_exists")
    row = BillingPlanVersion(
        plan_id=plan_id,
        version_code=code,
        name=(name or "").strip() or code,
        price_month=Decimal(str(price_month)),
        currency=(currency or "RUB").strip().upper() or "RUB",
        limits_json=_normalize_limits_payload(limits_json),
        features_json=_normalize_features_payload(features_json),
        valid_from=valid_from,
        valid_to=valid_to,
        is_active=bool(is_active),
        is_default_for_new_accounts=bool(is_default_for_new_accounts),
    )
    if row.is_default_for_new_accounts:
        _clear_default_versions(db, plan_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _plan_version_payload(row)


def update_billing_plan_version(
    db: Session,
    *,
    version_id: int,
    name: str | None = None,
    price_month: float | None = None,
    currency: str | None = None,
    limits_json: dict[str, Any] | None = None,
    features_json: dict[str, Any] | None = None,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    is_active: bool | None = None,
    is_default_for_new_accounts: bool | None = None,
) -> dict[str, Any]:
    row = db.get(BillingPlanVersion, version_id)
    if not row:
        raise ValueError("plan_version_not_found")
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
    if valid_from is not None:
        row.valid_from = valid_from
    if valid_to is not None:
        row.valid_to = valid_to
    if is_active is not None:
        row.is_active = bool(is_active)
    if is_default_for_new_accounts is not None:
        row.is_default_for_new_accounts = bool(is_default_for_new_accounts)
        if row.is_default_for_new_accounts:
            _clear_default_versions(db, int(row.plan_id), exclude_version_id=int(row.id))
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _plan_version_payload(row)


def set_billing_plan_version_active(db: Session, *, version_id: int, is_active: bool) -> dict[str, Any]:
    return update_billing_plan_version(db, version_id=version_id, is_active=is_active)


def set_billing_plan_version_default(db: Session, *, version_id: int) -> dict[str, Any]:
    return update_billing_plan_version(db, version_id=version_id, is_default_for_new_accounts=True)


def upsert_account_subscription(
    db: Session,
    *,
    account_id: int,
    plan_id: int,
    status: str,
    plan_version_id: int | None = None,
    billing_cycle: str | None = None,
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
    if billing_cycle is not None and billing_cycle not in {"monthly", "annual"}:
        raise ValueError("invalid_billing_cycle")
    if plan_version_id is not None:
        version = db.get(BillingPlanVersion, plan_version_id)
        if not version:
            raise ValueError("plan_version_not_found")
        if int(version.plan_id) != int(plan_id):
            raise ValueError("plan_version_plan_mismatch")
    else:
        version = db.execute(
            select(BillingPlanVersion)
            .where(BillingPlanVersion.plan_id == plan_id)
            .where(BillingPlanVersion.is_active.is_(True))
            .order_by(desc(BillingPlanVersion.is_default_for_new_accounts), desc(BillingPlanVersion.id))
            .limit(1)
        ).scalars().first()
    row = get_active_subscription(db, account_id)
    if row is None:
        row = AccountSubscription(account_id=account_id, plan_id=plan_id)
        db.add(row)
    row.plan_id = plan_id
    row.plan_version_id = int(version.id) if version else None
    row.status = status
    if billing_cycle is not None:
        row.billing_cycle = billing_cycle
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
