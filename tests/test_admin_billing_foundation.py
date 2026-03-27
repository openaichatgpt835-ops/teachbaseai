"""Admin billing foundation endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from apps.backend.auth import create_access_token
from apps.backend.database import Base, get_test_engine
from apps.backend.deps import get_db
from apps.backend.main import app
from apps.backend.models.account import Account, AccountIntegration, AppUser, AppUserWebCredential
from apps.backend.models.kb import KBChunk, KBFile
from apps.backend.models.portal import Portal
from apps.backend.models.billing import AccountPlanOverride, AccountSubscription, BillingPlan
from apps.backend.services.billing import (
    ensure_base_plans,
    get_account_bitrix_portal_count,
    is_account_bitrix_portal_limit_reached,
    would_exceed_account_media_minutes,
)


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


@pytest.mark.timeout(10)
def test_admin_billing_plans_seeded(test_db_session, override_get_db):
    app.dependency_overrides[get_db] = override_get_db
    try:
        admin_token = create_access_token({"sub": "admin"})
        resp = client.get("/v1/admin/billing/plans", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        codes = [item["code"] for item in data["items"]]
        assert codes == ["start", "business", "pro"]
        start = next(item for item in data["items"] if item["code"] == "start")
        business = next(item for item in data["items"] if item["code"] == "business")
        pro = next(item for item in data["items"] if item["code"] == "pro")
        assert start["limits"]["max_bitrix_portals"] == 1
        assert business["limits"]["max_bitrix_portals"] == 1
        assert pro["limits"]["max_bitrix_portals"] == 5
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.timeout(10)
def test_admin_billing_effective_policy_uses_override(test_db_session, override_get_db):
    app.dependency_overrides[get_db] = override_get_db
    try:
        admin_token = create_access_token({"sub": "admin"})
        account = Account(name="Test Account", status="active")
        test_db_session.add(account)
        test_db_session.commit()
        test_db_session.refresh(account)

        client.get("/v1/admin/billing/plans", headers={"Authorization": f"Bearer {admin_token}"})
        business_plan = test_db_session.query(BillingPlan).filter(BillingPlan.code == "business").one()
        test_db_session.add(
            AccountSubscription(
                account_id=account.id,
                plan_id=business_plan.id,
                status="active",
                started_at=datetime.utcnow(),
            )
        )
        test_db_session.add(
            AccountPlanOverride(
                account_id=account.id,
                limits_json={"requests_per_month": 777},
                features_json={"allow_speaker_diarization": True},
                valid_from=datetime.utcnow() - timedelta(days=1),
                valid_to=datetime.utcnow() + timedelta(days=1),
                reason="promo",
                created_by="admin@test",
            )
        )
        test_db_session.commit()

        resp = client.get(
            f"/v1/admin/billing/accounts/{account.id}/effective-policy",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "override"
        assert data["plan_code"] == "business"
        assert data["limits"]["requests_per_month"] == 777
        assert data["features"]["allow_speaker_diarization"] is True
        assert data["override"]["reason"] == "promo"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.timeout(10)
def test_admin_billing_create_plan_and_activate_toggle(test_db_session, override_get_db):
    app.dependency_overrides[get_db] = override_get_db
    try:
        admin_token = create_access_token({"sub": "admin"})
        resp = client.post(
            "/v1/admin/billing/plans",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "code": "enterprise",
                "name": "Enterprise",
                "price_month": 99900,
                "currency": "rub",
                "limits": {"requests_per_month": 100000, "media_minutes_per_month": 2500, "max_users": 500, "max_storage_gb": 1000},
                "features": {
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
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "enterprise"
        assert data["currency"] == "RUB"

        plan_id = data["id"]
        deactivated = client.post(
            f"/v1/admin/billing/plans/{plan_id}/deactivate",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert deactivated.status_code == 200
        assert deactivated.json()["is_active"] is False
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.timeout(10)
def test_admin_billing_subscription_and_override_crud(test_db_session, override_get_db):
    app.dependency_overrides[get_db] = override_get_db
    try:
        admin_token = create_access_token({"sub": "admin@example.com"})
        account = Account(name="Billing CRUD", status="active")
        test_db_session.add(account)
        test_db_session.commit()
        test_db_session.refresh(account)

        plans = client.get("/v1/admin/billing/plans", headers={"Authorization": f"Bearer {admin_token}"}).json()["items"]
        pro_plan = next(item for item in plans if item["code"] == "pro")

        subscription = client.put(
            f"/v1/admin/billing/accounts/{account.id}/subscription",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"plan_id": pro_plan["id"], "status": "active"},
        )
        assert subscription.status_code == 200
        assert subscription.json()["subscription"]["plan"]["code"] == "pro"

        override = client.post(
            f"/v1/admin/billing/accounts/{account.id}/overrides",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "limits": {"requests_per_month": 12345},
                "features": {"allow_speaker_diarization": False},
                "reason": "manual override",
            },
        )
        assert override.status_code == 200
        override_id = override.json()["id"]

        listed = client.get(
            f"/v1/admin/billing/accounts/{account.id}/overrides",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert listed.status_code == 200
        assert listed.json()["items"][0]["id"] == override_id

        updated = client.put(
            f"/v1/admin/billing/accounts/{account.id}/overrides/{override_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"features": {"allow_speaker_diarization": True}, "reason": "updated"},
        )
        assert updated.status_code == 200
        assert updated.json()["features"]["allow_speaker_diarization"] is True

        deleted = client.delete(
            f"/v1/admin/billing/accounts/{account.id}/overrides/{override_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.timeout(10)
def test_admin_billing_accounts_list_includes_subscription(test_db_session, override_get_db):
    app.dependency_overrides[get_db] = override_get_db
    try:
        admin_token = create_access_token({"sub": "admin@example.com"})
        owner = AppUser(display_name="Owner")
        test_db_session.add(owner)
        test_db_session.commit()
        test_db_session.refresh(owner)
        test_db_session.add(
            AppUserWebCredential(
                user_id=owner.id,
                login="owner@example.com",
                email="owner@example.com",
                password_hash="x",
            )
        )
        account = Account(name="Revenue Account", status="active", owner_user_id=owner.id, account_no=100123)
        test_db_session.add(account)
        test_db_session.commit()
        test_db_session.refresh(account)

        plans = client.get("/v1/admin/billing/plans", headers={"Authorization": f"Bearer {admin_token}"}).json()["items"]
        business_plan = next(item for item in plans if item["code"] == "business")
        client.put(
            f"/v1/admin/billing/accounts/{account.id}/subscription",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"plan_id": business_plan["id"], "status": "active"},
        )

        resp = client.get("/v1/admin/billing/accounts", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        row = next(item for item in resp.json()["items"] if item["id"] == account.id)
        assert row["owner_email"] == "owner@example.com"
        assert row["subscription"]["plan"]["code"] == "business"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.timeout(10)
def test_account_media_minutes_limit_uses_account_usage(test_db_session, override_get_db):
    account = Account(name="Media Account", status="active")
    test_db_session.add(account)
    test_db_session.flush()
    portal = Portal(domain="media.bitrix24.ru", status="active", account_id=account.id)
    test_db_session.add(portal)
    test_db_session.flush()
    ensure_base_plans(test_db_session)
    business_plan = test_db_session.query(BillingPlan).filter(BillingPlan.code == "business").one()
    test_db_session.add(
        AccountSubscription(
            account_id=account.id,
            plan_id=business_plan.id,
            status="active",
            started_at=datetime.utcnow(),
        )
    )
    for idx, end_ms in enumerate([120 * 60000, 100 * 60000]):
        file_row = KBFile(
            portal_id=portal.id,
            filename=f"media_{idx}.mp4",
            storage_path=f"/tmp/media_{idx}.mp4",
            size_bytes=1024,
            status="ready",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        test_db_session.add(file_row)
        test_db_session.flush()
        test_db_session.add(
            KBChunk(
                portal_id=portal.id,
                file_id=file_row.id,
                chunk_index=0,
                text="segment",
                end_ms=end_ms,
                created_at=datetime.utcnow(),
            )
        )
    test_db_session.commit()

    assert would_exceed_account_media_minutes(test_db_session, int(account.id), additional_minutes=90) is True
    assert would_exceed_account_media_minutes(test_db_session, int(account.id), additional_minutes=70) is False


@pytest.mark.timeout(10)
def test_account_bitrix_portal_limit_uses_account_policy(test_db_session, override_get_db):
    account = Account(name="Bitrix Limit", status="active")
    test_db_session.add(account)
    test_db_session.flush()
    ensure_base_plans(test_db_session)
    start_plan = test_db_session.query(BillingPlan).filter(BillingPlan.code == "start").one()
    pro_plan = test_db_session.query(BillingPlan).filter(BillingPlan.code == "pro").one()

    test_db_session.add(
        AccountSubscription(
            account_id=account.id,
            plan_id=start_plan.id,
            status="active",
            started_at=datetime.utcnow(),
        )
    )
    test_db_session.add_all(
        [
            AccountIntegration(
                account_id=account.id,
                provider="bitrix",
                external_key="b24-a.bitrix24.ru",
                status="active",
            ),
            AccountIntegration(
                account_id=account.id,
                provider="amo",
                external_key="amo-1",
                status="active",
            ),
        ]
    )
    test_db_session.commit()

    assert get_account_bitrix_portal_count(test_db_session, int(account.id)) == 1
    assert is_account_bitrix_portal_limit_reached(test_db_session, int(account.id), extra_portals=1) is True
    assert is_account_bitrix_portal_limit_reached(test_db_session, int(account.id), extra_portals=0) is False

    subscription = test_db_session.query(AccountSubscription).filter(AccountSubscription.account_id == account.id).one()
    subscription.plan_id = pro_plan.id
    test_db_session.commit()

    assert is_account_bitrix_portal_limit_reached(test_db_session, int(account.id), extra_portals=1) is False
