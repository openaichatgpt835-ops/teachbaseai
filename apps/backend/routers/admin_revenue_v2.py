"""Admin revenue v2 endpoints: plans, versions, accounts, effective policies."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.backend.auth import get_current_admin
from apps.backend.deps import get_db
from apps.backend.services.billing import (
    create_account_adjustment_v2,
    create_billing_plan,
    create_billing_plan_version,
    delete_account_adjustment_v2,
    get_account_effective_commercial_policy_v2,
    get_account_effective_runtime_policy_v2,
    get_account_revenue_detail_v2,
    list_billing_plan_versions,
    list_billing_plans_v2,
    list_account_adjustments_v2,
    list_revenue_accounts_v2,
    set_billing_plan_version_active,
    set_billing_plan_version_default,
    update_billing_plan,
    update_billing_plan_version,
    update_account_adjustment_v2,
    upsert_account_subscription,
)

router = APIRouter()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _bad_request(exc: ValueError) -> None:
    raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/plans")
def revenue_list_plans(
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return {"items": list_billing_plans_v2(db)}


@router.post("/plans")
def revenue_create_plan(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return create_billing_plan(
            db,
            code=str(payload.get("code") or ""),
            name=str(payload.get("name") or ""),
            price_month=float(payload.get("price_month") or 0),
            currency=str(payload.get("currency") or "RUB"),
            limits_json=payload.get("limits_json") or payload.get("limits"),
            features_json=payload.get("features_json") or payload.get("features"),
            is_active=bool(payload.get("is_active", True)),
        )
    except ValueError as exc:
        _bad_request(exc)


@router.put("/plans/{plan_id}")
def revenue_update_plan(
    plan_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return update_billing_plan(
            db,
            plan_id=plan_id,
            name=payload.get("name"),
            price_month=payload.get("price_month"),
            currency=payload.get("currency"),
            limits_json=payload.get("limits_json") if "limits_json" in payload else payload.get("limits"),
            features_json=payload.get("features_json") if "features_json" in payload else payload.get("features"),
            is_active=payload.get("is_active"),
        )
    except ValueError as exc:
        _bad_request(exc)


@router.get("/plans/{plan_id}/versions")
def revenue_list_plan_versions(
    plan_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return {"items": list_billing_plan_versions(db, plan_id)}


@router.post("/plans/{plan_id}/versions")
def revenue_create_plan_version(
    plan_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return create_billing_plan_version(
            db,
            plan_id=plan_id,
            version_code=str(payload.get("version_code") or ""),
            name=str(payload.get("name") or ""),
            price_month=float(payload.get("price_month") or 0),
            currency=str(payload.get("currency") or "RUB"),
            limits_json=payload.get("limits_json") or payload.get("limits"),
            features_json=payload.get("features_json") or payload.get("features"),
            valid_from=_parse_dt(payload.get("valid_from")),
            valid_to=_parse_dt(payload.get("valid_to")),
            is_active=bool(payload.get("is_active", True)),
            is_default_for_new_accounts=bool(payload.get("is_default_for_new_accounts", False)),
        )
    except ValueError as exc:
        _bad_request(exc)


@router.put("/plan-versions/{version_id}")
def revenue_update_plan_version(
    version_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return update_billing_plan_version(
            db,
            version_id=version_id,
            name=payload.get("name"),
            price_month=payload.get("price_month"),
            currency=payload.get("currency"),
            limits_json=payload.get("limits_json") if "limits_json" in payload else payload.get("limits"),
            features_json=payload.get("features_json") if "features_json" in payload else payload.get("features"),
            valid_from=_parse_dt(payload.get("valid_from")) if "valid_from" in payload else None,
            valid_to=_parse_dt(payload.get("valid_to")) if "valid_to" in payload else None,
            is_active=payload.get("is_active"),
            is_default_for_new_accounts=payload.get("is_default_for_new_accounts"),
        )
    except ValueError as exc:
        _bad_request(exc)


@router.post("/plan-versions/{version_id}/activate")
def revenue_activate_plan_version(
    version_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return set_billing_plan_version_active(db, version_id=version_id, is_active=True)
    except ValueError as exc:
        _bad_request(exc)


@router.post("/plan-versions/{version_id}/deactivate")
def revenue_deactivate_plan_version(
    version_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return set_billing_plan_version_active(db, version_id=version_id, is_active=False)
    except ValueError as exc:
        _bad_request(exc)


@router.post("/plan-versions/{version_id}/set-default")
def revenue_set_plan_version_default(
    version_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return set_billing_plan_version_default(db, version_id=version_id)
    except ValueError as exc:
        _bad_request(exc)


@router.get("/accounts")
def revenue_list_accounts(
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return {"items": list_revenue_accounts_v2(db, limit=limit)}


@router.get("/accounts/{account_id}")
def revenue_get_account(
    account_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return get_account_revenue_detail_v2(db, account_id)
    except ValueError as exc:
        _bad_request(exc)


@router.put("/accounts/{account_id}/subscription")
def revenue_upsert_subscription(
    account_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return upsert_account_subscription(
            db,
            account_id=account_id,
            plan_id=int(payload.get("plan_id")),
            plan_version_id=int(payload["plan_version_id"]) if payload.get("plan_version_id") is not None else None,
            status=str(payload.get("status") or "active"),
            billing_cycle=str(payload.get("billing_cycle") or "monthly"),
            trial_until=_parse_dt(payload.get("trial_until")),
            started_at=_parse_dt(payload.get("started_at")),
            ended_at=_parse_dt(payload.get("ended_at")),
        )
    except ValueError as exc:
        _bad_request(exc)


@router.get("/accounts/{account_id}/effective-runtime-policy")
def revenue_get_account_runtime_policy(
    account_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return get_account_effective_runtime_policy_v2(db, account_id)
    except ValueError as exc:
        _bad_request(exc)


@router.get("/accounts/{account_id}/effective-commercial-policy")
def revenue_get_account_commercial_policy(
    account_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return get_account_effective_commercial_policy_v2(db, account_id)
    except ValueError as exc:
        _bad_request(exc)


@router.get("/accounts/{account_id}/adjustments")
def revenue_list_account_adjustments(
    account_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return {"items": list_account_adjustments_v2(db, account_id)}


@router.post("/accounts/{account_id}/adjustments")
def revenue_create_account_adjustment(
    account_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    try:
        created_by = admin.get("sub") if isinstance(admin, dict) else None
        return create_account_adjustment_v2(
            db,
            account_id=account_id,
            kind=str(payload.get("kind") or ""),
            target_key=payload.get("target_key"),
            value_json=payload.get("value_json") if "value_json" in payload else payload.get("value"),
            valid_from=_parse_dt(payload.get("valid_from")),
            valid_to=_parse_dt(payload.get("valid_to")),
            reason=payload.get("reason"),
            created_by=created_by,
        )
    except ValueError as exc:
        _bad_request(exc)


@router.put("/accounts/{account_id}/adjustments/{adjustment_id}")
def revenue_update_account_adjustment(
    account_id: int,
    adjustment_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    del account_id
    try:
        return update_account_adjustment_v2(
            db,
            adjustment_id=adjustment_id,
            target_key=payload.get("target_key") if "target_key" in payload else None,
            value_json=payload.get("value_json") if "value_json" in payload else payload.get("value"),
            valid_from=_parse_dt(payload.get("valid_from")) if "valid_from" in payload else None,
            valid_to=_parse_dt(payload.get("valid_to")) if "valid_to" in payload else None,
            reason=payload.get("reason") if "reason" in payload else None,
        )
    except ValueError as exc:
        _bad_request(exc)


@router.delete("/accounts/{account_id}/adjustments/{adjustment_id}")
def revenue_delete_account_adjustment(
    account_id: int,
    adjustment_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    del account_id
    try:
        return delete_account_adjustment_v2(db, adjustment_id=adjustment_id)
    except ValueError as exc:
        _bad_request(exc)
