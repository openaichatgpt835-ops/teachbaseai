"""Admin revenue v2 YooKassa sandbox endpoints."""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from apps.backend.auth import create_access_token
from apps.backend.database import Base, get_test_engine
from apps.backend.deps import get_db
from apps.backend.main import app
from apps.backend.models.account import Account
from apps.backend.models.billing import BillingPlan, BillingPlanVersion
from apps.backend.services import billing_payments


client = TestClient(app)


@pytest.fixture
def test_db_session():
    engine = get_test_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def override_get_db(test_db_session):
    def _get_db():
        try:
            yield test_db_session
        finally:
            pass

    return _get_db


def _seed_plan_with_version(db):
    plan = BillingPlan(
        code="business",
        name="Business",
        is_active=True,
        price_month=14900,
        currency="RUB",
        limits_json={"requests_per_month": 5000, "max_users": 20},
        features_json={"allow_webhooks": True},
    )
    db.add(plan)
    db.flush()
    version = BillingPlanVersion(
        plan_id=plan.id,
        version_code="business-2026-04",
        name="Business 2026-04",
        price_month=14900,
        currency="RUB",
        limits_json={"requests_per_month": 5000, "max_users": 20},
        features_json={"allow_webhooks": True},
        is_active=True,
        is_default_for_new_accounts=True,
    )
    db.add(version)
    account = Account(name="Sandbox Account", status="active")
    db.add(account)
    db.commit()
    db.refresh(plan)
    db.refresh(version)
    db.refresh(account)
    return plan, version, account


class _StubClient:
    def create_payment(self, *, payload, idempotence_key):
        return {
            "id": "pay_test_1",
            "status": "pending",
            "paid": False,
            "test": True,
            "confirmation": {"type": "redirect", "confirmation_url": "https://yookassa.test/confirm"},
            "metadata": payload.get("metadata") or {},
        }

    def get_payment(self, payment_id: str):
        return {
            "id": payment_id,
            "status": "succeeded",
            "paid": True,
            "test": True,
        }


@pytest.mark.timeout(10)
def test_admin_revenue_v2_create_and_refresh_payment_attempt(test_db_session, override_get_db, monkeypatch):
    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(billing_payments, "_get_client", lambda: _StubClient())
    settings = billing_payments.get_settings()
    settings.yookassa_shop_id = "shop"
    settings.yookassa_secret_key = "secret"
    settings.public_base_url = "https://example.test"
    settings.yookassa_return_url = "https://example.test/app/billing"
    try:
        admin_token = create_access_token({"sub": "admin@example.com"})
        plan, version, account = _seed_plan_with_version(test_db_session)

        created = client.post(
            f"/v1/admin/revenue/accounts/{account.id}/payments",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "plan_id": plan.id,
                "plan_version_id": version.id,
            },
        )
        assert created.status_code == 200, created.text
        payload = created.json()
        assert payload["provider"] == "yookassa"
        assert payload["status"] == "pending"
        assert payload["provider_payment_id"] == "pay_test_1"
        assert payload["confirmation_url"] == "https://yookassa.test/confirm"

        refreshed = client.post(
            f"/v1/admin/revenue/payments/{payload['id']}/refresh",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert refreshed.status_code == 200, refreshed.text
        refreshed_payload = refreshed.json()
        assert refreshed_payload["status"] == "succeeded"
        assert refreshed_payload["paid"] is True

        account_detail = client.get(
            f"/v1/admin/revenue/accounts/{account.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert account_detail.status_code == 200, account_detail.text
        assert account_detail.json()["subscription"]["plan"]["id"] == plan.id
        assert account_detail.json()["subscription"]["plan_version"]["id"] == version.id
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.timeout(10)
def test_yookassa_webhook_matches_attempt(test_db_session, override_get_db, monkeypatch):
    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(billing_payments, "_get_client", lambda: _StubClient())
    settings = billing_payments.get_settings()
    settings.yookassa_shop_id = "shop"
    settings.yookassa_secret_key = "secret"
    settings.public_base_url = "https://example.test"
    settings.yookassa_return_url = "https://example.test/app/billing"
    try:
        admin_token = create_access_token({"sub": "admin@example.com"})
        plan, version, account = _seed_plan_with_version(test_db_session)

        created = client.post(
            f"/v1/admin/revenue/accounts/{account.id}/payments",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"plan_id": plan.id, "plan_version_id": version.id},
        )
        assert created.status_code == 200, created.text
        attempt = created.json()

        webhook = client.post(
            "/v1/billing/yookassa/webhook",
            json={
                "event": "payment.succeeded",
                "object": {
                    "id": "pay_test_1",
                    "status": "succeeded",
                    "paid": True,
                    "test": True,
                    "metadata": {
                        "attempt_id": str(attempt["id"]),
                    },
                },
            },
        )
        assert webhook.status_code == 200, webhook.text
        data = webhook.json()
        assert data["accepted"] is True
        assert data["matched"] is True
        assert data["attempt_id"] == attempt["id"]

        detail = client.get(
            f"/v1/admin/revenue/payments/{attempt['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["status"] == "succeeded"
        assert detail.json()["paid"] is True
    finally:
        app.dependency_overrides.pop(get_db, None)
