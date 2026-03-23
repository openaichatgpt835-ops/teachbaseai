"""Admin billing endpoints: usage, limits, pricing, plans."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.backend.auth import get_current_admin
from apps.backend.deps import get_db
from apps.backend.models.billing import BillingUsage
from apps.backend.services.billing import (
    create_account_plan_override,
    create_billing_plan,
    delete_account_plan_override,
    get_account_effective_policy,
    get_account_subscription_payload,
    list_billing_accounts,
    get_portal_limit,
    get_portal_usage_summary,
    get_pricing,
    list_account_plan_overrides,
    list_billing_plans,
    set_billing_plan_active,
    set_portal_limit,
    set_pricing,
    update_account_plan_override,
    update_billing_plan,
    upsert_account_subscription,
)

router = APIRouter()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _bad_request(exc: ValueError) -> None:
    raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/pricing')
def billing_get_pricing(
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return get_pricing(db)


@router.post('/pricing')
def billing_set_pricing(
    chat_rub_per_1k: float | None = Body(None),
    embed_rub_per_1k: float | None = Body(None),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return set_pricing(db, chat_rub_per_1k, embed_rub_per_1k)


@router.get('/plans')
def billing_list_plans(
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return {'items': list_billing_plans(db)}


@router.get('/accounts')
def billing_list_accounts(
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return {'items': list_billing_accounts(db, limit=limit)}


@router.post('/plans')
def billing_create_plan(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return create_billing_plan(
            db,
            code=str(payload.get('code') or ''),
            name=str(payload.get('name') or ''),
            price_month=float(payload.get('price_month') or 0),
            currency=str(payload.get('currency') or 'RUB'),
            limits_json=payload.get('limits_json') or payload.get('limits'),
            features_json=payload.get('features_json') or payload.get('features'),
            is_active=bool(payload.get('is_active', True)),
        )
    except ValueError as exc:
        _bad_request(exc)


@router.put('/plans/{plan_id}')
def billing_update_plan(
    plan_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return update_billing_plan(
            db,
            plan_id=plan_id,
            name=payload.get('name'),
            price_month=payload.get('price_month'),
            currency=payload.get('currency'),
            limits_json=payload.get('limits_json') if 'limits_json' in payload else payload.get('limits'),
            features_json=payload.get('features_json') if 'features_json' in payload else payload.get('features'),
            is_active=payload.get('is_active'),
        )
    except ValueError as exc:
        _bad_request(exc)


@router.post('/plans/{plan_id}/activate')
def billing_activate_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return set_billing_plan_active(db, plan_id=plan_id, is_active=True)
    except ValueError as exc:
        _bad_request(exc)


@router.post('/plans/{plan_id}/deactivate')
def billing_deactivate_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return set_billing_plan_active(db, plan_id=plan_id, is_active=False)
    except ValueError as exc:
        _bad_request(exc)


@router.get('/accounts/{account_id}/subscription')
def billing_account_subscription(
    account_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return get_account_subscription_payload(db, account_id)


@router.put('/accounts/{account_id}/subscription')
def billing_upsert_subscription(
    account_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return upsert_account_subscription(
            db,
            account_id=account_id,
            plan_id=int(payload.get('plan_id')),
            status=str(payload.get('status') or 'active'),
            trial_until=_parse_dt(payload.get('trial_until')),
            started_at=_parse_dt(payload.get('started_at')),
            ended_at=_parse_dt(payload.get('ended_at')),
        )
    except ValueError as exc:
        _bad_request(exc)


@router.get('/accounts/{account_id}/overrides')
def billing_list_overrides(
    account_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return {'items': list_account_plan_overrides(db, account_id)}


@router.post('/accounts/{account_id}/overrides')
def billing_create_override(
    account_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    try:
        created_by = admin.get('sub') if isinstance(admin, dict) else None
        return create_account_plan_override(
            db,
            account_id=account_id,
            limits_json=payload.get('limits_json') or payload.get('limits'),
            features_json=payload.get('features_json') or payload.get('features'),
            valid_from=_parse_dt(payload.get('valid_from')),
            valid_to=_parse_dt(payload.get('valid_to')),
            reason=payload.get('reason'),
            created_by=created_by,
        )
    except ValueError as exc:
        _bad_request(exc)


@router.put('/accounts/{account_id}/overrides/{override_id}')
def billing_update_override(
    account_id: int,
    override_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    del account_id
    try:
        return update_account_plan_override(
            db,
            override_id=override_id,
            limits_json=payload.get('limits_json') if 'limits_json' in payload else payload.get('limits'),
            features_json=payload.get('features_json') if 'features_json' in payload else payload.get('features'),
            valid_from=_parse_dt(payload.get('valid_from')) if 'valid_from' in payload else None,
            valid_to=_parse_dt(payload.get('valid_to')) if 'valid_to' in payload else None,
            reason=payload.get('reason'),
        )
    except ValueError as exc:
        _bad_request(exc)


@router.delete('/accounts/{account_id}/overrides/{override_id}')
def billing_delete_override(
    account_id: int,
    override_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    del account_id
    try:
        return delete_account_plan_override(db, override_id=override_id)
    except ValueError as exc:
        _bad_request(exc)


@router.get('/accounts/{account_id}/effective-policy')
def billing_account_effective_policy(
    account_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return get_account_effective_policy(db, account_id)


@router.get('/portals/{portal_id}/summary')
def billing_portal_summary(
    portal_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    summary = get_portal_usage_summary(db, portal_id)
    summary['monthly_request_limit'] = get_portal_limit(db, portal_id)
    return summary


@router.post('/portals/{portal_id}/limit')
def billing_set_portal_limit(
    portal_id: int,
    monthly_request_limit: int | None = Body(None),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return {'portal_id': portal_id, 'monthly_request_limit': set_portal_limit(db, portal_id, monthly_request_limit)}


@router.get('/usage')
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
        'items': [
            {
                'id': r.id,
                'portal_id': r.portal_id,
                'user_id': r.user_id,
                'request_id': r.request_id,
                'kind': r.kind,
                'model': r.model,
                'tokens_prompt': r.tokens_prompt,
                'tokens_completion': r.tokens_completion,
                'tokens_total': r.tokens_total,
                'cost_rub': float(r.cost_rub or 0),
                'status': r.status,
                'error_code': r.error_code,
                'created_at': r.created_at.isoformat() if r.created_at else None,
            }
            for r in items
        ]
    }
