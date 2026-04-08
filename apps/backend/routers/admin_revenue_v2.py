"""Admin revenue v2 endpoints: plans, versions, accounts, effective policies."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.backend.auth import get_current_admin
from apps.backend.deps import get_db
from apps.backend.services.billing import (
    assign_account_to_cohort_v2,
    create_account_adjustment_v2,
    create_billing_plan,
    create_billing_plan_version,
    create_revenue_cohort_v2,
    delete_account_adjustment_v2,
    get_account_effective_commercial_policy_v2,
    get_account_effective_runtime_policy_v2,
    get_account_revenue_detail_v2,
    list_revenue_cohort_accounts_v2,
    list_revenue_cohorts_v2,
    list_billing_plan_versions,
    list_billing_plans_v2,
    list_account_adjustments_v2,
    list_revenue_accounts_v2,
    set_billing_plan_version_active,
    set_billing_plan_version_default,
    unassign_account_from_cohort_v2,
    update_billing_plan,
    update_billing_plan_version,
    update_account_adjustment_v2,
    update_revenue_cohort_v2,
    upsert_account_subscription,
    upsert_revenue_cohort_policy_v2,
)
from apps.backend.services.billing_payments import (
    create_yookassa_payment_attempt,
    get_payment_attempt_detail,
    get_yookassa_config_health,
    list_payment_attempts,
    refresh_yookassa_payment_attempt,
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


@router.get("/cohorts")
def revenue_list_cohorts(
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return {"items": list_revenue_cohorts_v2(db)}


@router.post("/cohorts")
def revenue_create_cohort(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return create_revenue_cohort_v2(
            db,
            code=str(payload.get("code") or ""),
            name=str(payload.get("name") or ""),
            description=payload.get("description"),
            rule_json=payload.get("rule_json") if "rule_json" in payload else payload.get("rule"),
            is_active=bool(payload.get("is_active", True)),
        )
    except ValueError as exc:
        _bad_request(exc)


@router.put("/cohorts/{cohort_id}")
def revenue_update_cohort(
    cohort_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return update_revenue_cohort_v2(
            db,
            cohort_id=cohort_id,
            name=payload.get("name"),
            description=payload.get("description"),
            rule_json=payload.get("rule_json") if "rule_json" in payload else payload.get("rule"),
            is_active=payload.get("is_active"),
        )
    except ValueError as exc:
        _bad_request(exc)


@router.get("/cohorts/{cohort_id}/accounts")
def revenue_list_cohort_accounts(
    cohort_id: int,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return {"items": list_revenue_cohort_accounts_v2(db, cohort_id, limit=limit)}
    except ValueError as exc:
        _bad_request(exc)


@router.put("/cohorts/{cohort_id}/policy")
def revenue_upsert_cohort_policy(
    cohort_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return upsert_revenue_cohort_policy_v2(
            db,
            cohort_id=cohort_id,
            plan_version_id=int(payload.get("plan_version_id")),
            discount_type=payload.get("discount_type"),
            discount_value=payload.get("discount_value"),
            feature_adjustments_json=payload.get("feature_adjustments_json")
            if "feature_adjustments_json" in payload
            else payload.get("features"),
            limit_adjustments_json=payload.get("limit_adjustments_json")
            if "limit_adjustments_json" in payload
            else payload.get("limits"),
            valid_from=_parse_dt(payload.get("valid_from")),
            valid_to=_parse_dt(payload.get("valid_to")),
            is_active=bool(payload.get("is_active", True)),
        )
    except ValueError as exc:
        _bad_request(exc)


@router.post("/cohorts/{cohort_id}/accounts/{account_id}")
def revenue_assign_account_to_cohort(
    cohort_id: int,
    account_id: int,
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    try:
        created_by = admin.get("sub") if isinstance(admin, dict) else None
        return assign_account_to_cohort_v2(
            db,
            cohort_id=cohort_id,
            account_id=account_id,
            reason=payload.get("reason"),
            created_by=created_by,
        )
    except ValueError as exc:
        _bad_request(exc)


@router.delete("/cohorts/{cohort_id}/accounts/{account_id}")
def revenue_unassign_account_from_cohort(
    cohort_id: int,
    account_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return unassign_account_from_cohort_v2(db, cohort_id=cohort_id, account_id=account_id)
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


@router.get("/payments/health")
def revenue_payments_health(
    _: dict = Depends(get_current_admin),
):
    return get_yookassa_config_health()


@router.get("/payments")
def revenue_list_payment_attempts(
    account_id: int | None = Query(default=None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return {"items": list_payment_attempts(db, account_id=account_id, limit=limit)}


@router.get("/payments/{attempt_id}")
def revenue_get_payment_attempt(
    attempt_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return get_payment_attempt_detail(db, attempt_id)
    except ValueError as exc:
        _bad_request(exc)


@router.post("/accounts/{account_id}/payments")
def revenue_create_payment_attempt(
    account_id: int,
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    try:
        created_by = admin.get("sub") if isinstance(admin, dict) else None
        return create_yookassa_payment_attempt(
            db,
            account_id=account_id,
            plan_id=int(payload["plan_id"]) if payload.get("plan_id") is not None else None,
            plan_version_id=int(payload["plan_version_id"]) if payload.get("plan_version_id") is not None else None,
            amount=float(payload["amount"]) if payload.get("amount") is not None else None,
            currency=payload.get("currency"),
            description=payload.get("description"),
            return_url=payload.get("return_url"),
            created_by=created_by,
        )
    except ValueError as exc:
        _bad_request(exc)


@router.post("/payments/{attempt_id}/refresh")
def revenue_refresh_payment_attempt(
    attempt_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    try:
        return refresh_yookassa_payment_attempt(db, attempt_id=attempt_id)
    except ValueError as exc:
        _bad_request(exc)
