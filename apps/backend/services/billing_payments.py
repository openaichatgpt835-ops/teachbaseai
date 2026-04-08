from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.backend.clients.yookassa import YooKassaClient
from apps.backend.config import get_settings
from apps.backend.models.account import Account
from apps.backend.models.billing import (
    AccountSubscription,
    BillingPaymentAttempt,
    BillingPlan,
    BillingPlanVersion,
)
from apps.backend.services.billing import (
    get_account_effective_commercial_policy_v2,
    get_account_subscription_payload,
    upsert_account_subscription,
)


def get_yookassa_config_health() -> dict[str, Any]:
    settings = get_settings()
    webhook_url = None
    if settings.public_base_url:
        webhook_url = f"{settings.public_base_url.rstrip('/')}/api/v1/billing/yookassa/webhook"
    return {
        "enabled": bool(settings.yookassa_shop_id and settings.yookassa_secret_key),
        "shop_id_configured": bool(settings.yookassa_shop_id),
        "secret_key_configured": bool(settings.yookassa_secret_key),
        "return_url": settings.yookassa_return_url or settings.public_base_url,
        "webhook_url": webhook_url,
    }


def _get_client() -> YooKassaClient:
    settings = get_settings()
    if not settings.yookassa_shop_id or not settings.yookassa_secret_key:
        raise ValueError("yookassa_not_configured")
    return YooKassaClient(shop_id=settings.yookassa_shop_id, secret_key=settings.yookassa_secret_key)


def _payment_attempt_payload(row: BillingPaymentAttempt | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": int(row.id),
        "account_id": int(row.account_id),
        "subscription_id": int(row.subscription_id) if row.subscription_id else None,
        "plan_id": int(row.plan_id) if row.plan_id else None,
        "plan_version_id": int(row.plan_version_id) if row.plan_version_id else None,
        "provider": row.provider,
        "idempotence_key": row.idempotence_key,
        "provider_payment_id": row.provider_payment_id,
        "status": row.status,
        "amount": float(row.amount or 0),
        "currency": row.currency,
        "description": row.description,
        "confirmation_url": row.confirmation_url,
        "return_url": row.return_url,
        "paid": bool(row.paid),
        "test": bool(row.test),
        "error_message": row.error_message,
        "provider_payload_json": dict(row.provider_payload_json or {}),
        "metadata_json": dict(row.metadata_json or {}),
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "succeeded_at": row.succeeded_at.isoformat() if row.succeeded_at else None,
        "canceled_at": row.canceled_at.isoformat() if row.canceled_at else None,
    }


def list_payment_attempts(db: Session, *, account_id: int | None = None, limit: int = 100) -> list[dict[str, Any]]:
    q = select(BillingPaymentAttempt).order_by(desc(BillingPaymentAttempt.created_at), desc(BillingPaymentAttempt.id)).limit(limit)
    if account_id is not None:
        q = q.where(BillingPaymentAttempt.account_id == account_id)
    rows = db.execute(q).scalars().all()
    return [_payment_attempt_payload(row) for row in rows if row]


def get_payment_attempt_detail(db: Session, attempt_id: int) -> dict[str, Any]:
    row = db.get(BillingPaymentAttempt, attempt_id)
    if not row:
        raise ValueError("payment_attempt_not_found")
    return _payment_attempt_payload(row)


def _resolve_payment_target(
    db: Session,
    *,
    account_id: int,
    plan_id: int | None,
    plan_version_id: int | None,
    amount: float | None,
    currency: str | None,
) -> dict[str, Any]:
    subscription = get_account_subscription_payload(db, account_id).get("subscription")
    plan = db.get(BillingPlan, plan_id) if plan_id else None
    version = db.get(BillingPlanVersion, plan_version_id) if plan_version_id else None

    if version and plan and int(version.plan_id) != int(plan.id):
        raise ValueError("plan_version_plan_mismatch")
    if version and not plan:
        plan = db.get(BillingPlan, int(version.plan_id))
    if not version and plan:
        version = db.execute(
            select(BillingPlanVersion)
            .where(BillingPlanVersion.plan_id == plan.id)
            .where(BillingPlanVersion.is_active.is_(True))
            .order_by(desc(BillingPlanVersion.is_default_for_new_accounts), desc(BillingPlanVersion.id))
            .limit(1)
        ).scalars().first()

    if not plan and subscription and subscription.get("plan"):
        plan = db.get(BillingPlan, int(subscription["plan"]["id"]))
    if not version and subscription and subscription.get("plan_version"):
        version = db.get(BillingPlanVersion, int(subscription["plan_version"]["id"]))

    commercial = get_account_effective_commercial_policy_v2(db, account_id)
    final_currency = (currency or (version.currency if version else None) or commercial.get("currency") or "RUB").upper()
    final_amount = amount
    if final_amount is None:
        if version is not None:
            final_amount = float(version.price_month or 0)
        elif commercial.get("final_price_month") is not None:
            final_amount = float(commercial["final_price_month"])
    if final_amount is None or final_amount <= 0:
        raise ValueError("payment_amount_required")

    return {
        "subscription_id": int(subscription["id"]) if subscription and subscription.get("id") else None,
        "plan": plan,
        "plan_version": version,
        "amount": final_amount,
        "currency": final_currency,
    }


def create_yookassa_payment_attempt(
    db: Session,
    *,
    account_id: int,
    plan_id: int | None = None,
    plan_version_id: int | None = None,
    amount: float | None = None,
    currency: str | None = None,
    description: str | None = None,
    return_url: str | None = None,
    created_by: str | None = None,
) -> dict[str, Any]:
    account = db.get(Account, account_id)
    if not account:
        raise ValueError("account_not_found")
    target = _resolve_payment_target(
        db,
        account_id=account_id,
        plan_id=plan_id,
        plan_version_id=plan_version_id,
        amount=amount,
        currency=currency,
    )
    settings = get_settings()
    effective_return_url = return_url or settings.yookassa_return_url or settings.public_base_url
    if not effective_return_url:
        raise ValueError("yookassa_return_url_required")

    attempt = BillingPaymentAttempt(
        account_id=account_id,
        subscription_id=target["subscription_id"],
        plan_id=int(target["plan"].id) if target["plan"] else None,
        plan_version_id=int(target["plan_version"].id) if target["plan_version"] else None,
        provider="yookassa",
        idempotence_key=str(uuid4()),
        status="pending",
        amount=Decimal(str(target["amount"])),
        currency=target["currency"],
        description=(description or f"Teachbase AI - {account.name or f'Account #{account.id}'}").strip(),
        return_url=effective_return_url,
        metadata_json={
            "account_id": str(account_id),
            "plan_id": str(target["plan"].id) if target["plan"] else None,
            "plan_version_id": str(target["plan_version"].id) if target["plan_version"] else None,
        },
        created_by=(created_by or "").strip() or None,
    )
    db.add(attempt)
    db.flush()

    payload = {
        "amount": {"value": f"{target['amount']:.2f}", "currency": target["currency"]},
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": effective_return_url},
        "description": attempt.description,
        "metadata": {
            "attempt_id": str(attempt.id),
            "account_id": str(account_id),
            "plan_id": str(target["plan"].id) if target["plan"] else "",
            "plan_version_id": str(target["plan_version"].id) if target["plan_version"] else "",
        },
    }

    try:
        response = _get_client().create_payment(payload=payload, idempotence_key=attempt.idempotence_key)
    except httpx.HTTPError as exc:
        attempt.status = "error"
        attempt.error_message = str(exc)
        attempt.provider_payload_json = {"error": str(exc)}
        db.commit()
        raise ValueError("yookassa_create_payment_failed") from exc

    attempt.provider_payment_id = str(response.get("id") or "") or None
    attempt.status = str(response.get("status") or "pending")
    attempt.confirmation_url = (
        response.get("confirmation", {}) or {}
    ).get("confirmation_url")
    attempt.paid = bool(response.get("paid"))
    attempt.test = bool(response.get("test"))
    attempt.provider_payload_json = response
    db.commit()
    db.refresh(attempt)
    return _payment_attempt_payload(attempt)


def refresh_yookassa_payment_attempt(db: Session, *, attempt_id: int) -> dict[str, Any]:
    row = db.get(BillingPaymentAttempt, attempt_id)
    if not row:
        raise ValueError("payment_attempt_not_found")
    if not row.provider_payment_id:
        raise ValueError("provider_payment_id_missing")
    try:
        payment = _get_client().get_payment(str(row.provider_payment_id))
    except httpx.HTTPError as exc:
        row.error_message = str(exc)
        row.updated_at = datetime.utcnow()
        db.commit()
        raise ValueError("yookassa_refresh_failed") from exc
    _apply_provider_payment_state(db, row=row, payment=payment, activate_subscription=True)
    db.commit()
    db.refresh(row)
    return _payment_attempt_payload(row)


def _apply_provider_payment_state(
    db: Session,
    *,
    row: BillingPaymentAttempt,
    payment: dict[str, Any],
    activate_subscription: bool,
) -> None:
    row.provider_payment_id = str(payment.get("id") or row.provider_payment_id or "") or None
    row.status = str(payment.get("status") or row.status)
    row.paid = bool(payment.get("paid"))
    row.test = bool(payment.get("test"))
    row.confirmation_url = ((payment.get("confirmation", {}) or {}).get("confirmation_url")) or row.confirmation_url
    row.provider_payload_json = payment
    row.updated_at = datetime.utcnow()

    status = row.status
    if status == "succeeded":
        row.succeeded_at = row.succeeded_at or datetime.utcnow()
        row.error_message = None
        if activate_subscription:
            if row.plan_id:
                upsert_account_subscription(
                    db,
                    account_id=int(row.account_id),
                    plan_id=int(row.plan_id),
                    plan_version_id=int(row.plan_version_id) if row.plan_version_id else None,
                    status="active",
                    billing_cycle="monthly",
                )
    elif status == "canceled":
        row.canceled_at = row.canceled_at or datetime.utcnow()


def handle_yookassa_webhook(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    event = str(payload.get("event") or "")
    obj = payload.get("object") or {}
    payment_id = str(obj.get("id") or "")
    attempt_id = int((obj.get("metadata") or {}).get("attempt_id") or 0) if (obj.get("metadata") or {}).get("attempt_id") else 0

    row = None
    if payment_id:
        row = db.execute(
            select(BillingPaymentAttempt).where(BillingPaymentAttempt.provider_payment_id == payment_id).limit(1)
        ).scalars().first()
    if row is None and attempt_id:
        row = db.get(BillingPaymentAttempt, attempt_id)
    if row is None:
        return {"accepted": True, "matched": False, "event": event}

    provider_payment = obj
    if payment_id:
        try:
            provider_payment = _get_client().get_payment(payment_id)
        except httpx.HTTPError:
            provider_payment = obj

    _apply_provider_payment_state(db, row=row, payment=provider_payment, activate_subscription=event == "payment.succeeded")
    db.commit()
    return {"accepted": True, "matched": True, "event": event, "attempt_id": int(row.id)}
