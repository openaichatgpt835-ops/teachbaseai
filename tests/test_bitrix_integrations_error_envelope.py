"""Bitrix integrations endpoints error envelope tests."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from apps.backend.main import app
from apps.backend.deps import get_db
from apps.backend.database import Base, get_test_engine
from apps.backend.models.account import Account
from apps.backend.models.billing import AccountPlanOverride, AccountSubscription, BillingPlan
from apps.backend.models.portal import Portal
from apps.backend.auth import create_portal_token_with_user, require_portal_access
from apps.backend.services.billing import ensure_base_plans

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
def test_bitrix_credentials_missing_fields_envelope(test_db_session, override_get_db):
    portal = Portal(domain="cred.bitrix24.ru", status="active", admin_user_id=1)
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)
    token = create_portal_token_with_user(portal.id, user_id=1, expires_minutes=10)

    app.dependency_overrides[get_db] = override_get_db
    try:
        r = client.post(
            f"/v1/bitrix/portals/{portal.id}/bitrix/credentials",
            headers={"Authorization": f"Bearer {token}"},
            json={"client_id": "", "client_secret": ""},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 400
    data = r.json()
    assert data.get("error") == "missing_credentials"
    assert data.get("code") == "missing_credentials"
    assert "trace_id" in data


@pytest.mark.timeout(10)
def test_kb_models_missing_token_envelope(test_db_session, override_get_db):
    portal = Portal(domain="models.bitrix24.ru", status="active", admin_user_id=1)
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)
    token = create_portal_token_with_user(portal.id, user_id=1, expires_minutes=10)

    app.dependency_overrides[get_db] = override_get_db
    try:
        r = client.get(
            f"/v1/bitrix/portals/{portal.id}/kb/models",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 400
    data = r.json()
    assert data.get("error")
    assert data.get("code")
    assert "trace_id" in data


@pytest.mark.timeout(10)
def test_telegram_client_settings_forbidden_envelope(test_db_session, override_get_db):
    p1 = Portal(domain="p1.bitrix24.ru", status="active", admin_user_id=1)
    p2 = Portal(domain="p2.bitrix24.ru", status="active", admin_user_id=1)
    test_db_session.add_all([p1, p2])
    test_db_session.commit()
    test_db_session.refresh(p1)
    test_db_session.refresh(p2)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_portal_access] = lambda: p1.id
    try:
        r = client.post(
            f"/v1/bitrix/portals/{p2.id}/telegram/client",
            json={"enabled": True},
        )
    finally:
        app.dependency_overrides.pop(require_portal_access, None)
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 403
    data = r.json()
    assert data.get("error") == "forbidden"
    assert data.get("code") == "forbidden"
    assert "trace_id" in data


@pytest.mark.timeout(10)
def test_bitrix_credentials_forbidden_envelope(test_db_session, override_get_db):
    p1 = Portal(domain="pc1.bitrix24.ru", status="active", admin_user_id=1)
    p2 = Portal(domain="pc2.bitrix24.ru", status="active", admin_user_id=1)
    test_db_session.add_all([p1, p2])
    test_db_session.commit()
    test_db_session.refresh(p1)
    test_db_session.refresh(p2)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_portal_access] = lambda: p1.id
    try:
        r = client.post(
            f"/v1/bitrix/portals/{p2.id}/bitrix/credentials",
            json={"client_id": "abc", "client_secret": "def"},
        )
    finally:
        app.dependency_overrides.pop(require_portal_access, None)
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 403
    data = r.json()
    assert data.get("error") == "forbidden"
    assert data.get("code") == "forbidden"
    assert "trace_id" in data


@pytest.mark.timeout(10)
def test_portal_billing_policy_endpoint_returns_feature_gates(test_db_session, override_get_db):
    account = Account(name="Policy account", status="active")
    test_db_session.add(account)
    test_db_session.commit()
    test_db_session.refresh(account)
    ensure_base_plans(test_db_session)
    start_plan = test_db_session.query(BillingPlan).filter(BillingPlan.code == "start").one()
    test_db_session.add(
        AccountSubscription(account_id=account.id, plan_id=start_plan.id, status="active", started_at=datetime.utcnow())
    )
    portal = Portal(domain="policy.bitrix24.ru", status="active", admin_user_id=1, account_id=account.id)
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)
    token = create_portal_token_with_user(portal.id, user_id=1, expires_minutes=10)

    app.dependency_overrides[get_db] = override_get_db
    try:
        r = client.get(
            f"/v1/bitrix/portals/{portal.id}/billing/policy",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    data = r.json()
    assert data["billing_policy"]["plan_code"] == "start"
    assert data["feature_gates"]["webhooks"]["allowed"] is False


@pytest.mark.timeout(10)
def test_telegram_client_settings_locked_by_plan(test_db_session, override_get_db):
    account = Account(name="Locked client bot", status="active")
    test_db_session.add(account)
    test_db_session.commit()
    test_db_session.refresh(account)
    ensure_base_plans(test_db_session)
    business_plan = test_db_session.query(BillingPlan).filter(BillingPlan.code == "business").one()
    test_db_session.add(
        AccountSubscription(account_id=account.id, plan_id=business_plan.id, status="active", started_at=datetime.utcnow())
    )
    test_db_session.add(
        AccountPlanOverride(
            account_id=account.id,
            features_json={"allow_client_bot": False},
            valid_from=datetime.utcnow() - timedelta(days=1),
            valid_to=datetime.utcnow() + timedelta(days=1),
            reason="test",
            created_by="test",
        )
    )
    portal = Portal(domain="tg-lock.bitrix24.ru", status="active", admin_user_id=1, account_id=account.id)
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)
    token = create_portal_token_with_user(portal.id, user_id=1, expires_minutes=10)

    app.dependency_overrides[get_db] = override_get_db
    try:
        r = client.post(
            f"/v1/bitrix/portals/{portal.id}/telegram/client",
            headers={"Authorization": f"Bearer {token}"},
            json={"enabled": True},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 403
    data = r.json()
    assert data.get("error") == "client_bot_locked"
    assert data.get("code") == "client_bot_locked"
