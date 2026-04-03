from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from apps.backend.auth import get_password_hash
from apps.backend.database import Base, get_test_engine
from apps.backend.deps import get_db
from apps.backend.main import app
from apps.backend.models.account import Account, AccountIntegration, AccountMembership, AccountPermission, AppUser, AppUserWebCredential
from apps.backend.models.billing import AccountSubscription, BillingPlan
from apps.backend.models.portal import Portal
from apps.backend.models.web_user import WebUser
from apps.backend.routers import bitrix as bitrix_router
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


def _override_get_db(db):
    def _get_db():
        try:
            yield db
        finally:
            pass

    return _get_db


def _seed_plan(db, account_id: int, code: str) -> None:
    ensure_base_plans(db)
    plan = db.query(BillingPlan).filter(BillingPlan.code == code).one()
    db.add(
        AccountSubscription(
            account_id=account_id,
            plan_id=plan.id,
            status="active",
            started_at=datetime.utcnow(),
        )
    )
    db.commit()


@pytest.mark.timeout(10)
def test_bitrix_link_precheck_blocks_member_attach(test_db_session):
    portal_b = Portal(domain="b24-b.bitrix24.ru", status="active", admin_user_id=1)
    portal_a = Portal(domain="b24-a.bitrix24.ru", status="active", admin_user_id=1)
    test_db_session.add_all([portal_a, portal_b])
    test_db_session.flush()

    web_user = WebUser(
        email="member@example.com",
        password_hash=get_password_hash("Secret123!"),
        portal_id=portal_a.id,
        email_verified_at=datetime.utcnow(),
    )
    test_db_session.add(web_user)
    test_db_session.flush()

    app_user = AppUser(display_name="Member", status="active")
    test_db_session.add(app_user)
    test_db_session.flush()
    test_db_session.add(
        AppUserWebCredential(
            user_id=app_user.id,
            login="member@example.com",
            email="member@example.com",
            password_hash=get_password_hash("Secret123!"),
            email_verified_at=datetime.utcnow(),
        )
    )

    account_a = Account(name="Account A", status="active", account_no=100001, owner_user_id=app_user.id)
    test_db_session.add(account_a)
    test_db_session.flush()
    portal_a.account_id = account_a.id
    membership = AccountMembership(account_id=account_a.id, user_id=app_user.id, role="member", status="active")
    test_db_session.add(membership)
    test_db_session.flush()
    test_db_session.add(
        AccountPermission(
            membership_id=membership.id,
            kb_access="read",
            can_invite_users=False,
            can_manage_settings=False,
            can_view_finance=False,
        )
    )
    test_db_session.add(
        AccountIntegration(
            account_id=account_a.id,
            provider="bitrix",
            status="active",
            external_key="b24-a.bitrix24.ru",
            portal_id=portal_a.id,
        )
    )
    test_db_session.commit()
    _seed_plan(test_db_session, account_a.id, "pro")

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    original_require_admin = bitrix_router._require_portal_admin
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    try:
        resp = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/web/link/precheck",
            json={"email": "member@example.com", "password": "Secret123!"},
        )
    finally:
        bitrix_router._require_portal_admin = original_require_admin
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["recommended_action"] == "upgrade_or_create"
    assert data["can_create_new_account"] is True
    assert len(data["attachable_accounts"]) == 1
    assert data["attachable_accounts"][0]["attach_allowed"] is False
    assert data["attachable_accounts"][0]["reason"] == "insufficient_role"


@pytest.mark.timeout(10)
def test_bitrix_link_precheck_blocks_attach_by_plan_limit(test_db_session):
    portal_b = Portal(domain="b24-b.bitrix24.ru", status="active", admin_user_id=1)
    portal_a = Portal(domain="b24-a.bitrix24.ru", status="active", admin_user_id=1)
    test_db_session.add_all([portal_a, portal_b])
    test_db_session.flush()

    web_user = WebUser(
        email="owner@example.com",
        password_hash=get_password_hash("Secret123!"),
        portal_id=portal_a.id,
        email_verified_at=datetime.utcnow(),
    )
    test_db_session.add(web_user)
    test_db_session.flush()

    app_user = AppUser(display_name="Owner", status="active")
    test_db_session.add(app_user)
    test_db_session.flush()
    test_db_session.add(
        AppUserWebCredential(
            user_id=app_user.id,
            login="owner@example.com",
            email="owner@example.com",
            password_hash=get_password_hash("Secret123!"),
            email_verified_at=datetime.utcnow(),
        )
    )

    account_a = Account(name="Account A", status="active", account_no=100002, owner_user_id=app_user.id)
    test_db_session.add(account_a)
    test_db_session.flush()
    portal_a.account_id = account_a.id
    membership = AccountMembership(account_id=account_a.id, user_id=app_user.id, role="owner", status="active")
    test_db_session.add(membership)
    test_db_session.flush()
    test_db_session.add(
        AccountPermission(
            membership_id=membership.id,
            kb_access="write",
            can_invite_users=True,
            can_manage_settings=True,
            can_view_finance=True,
        )
    )
    test_db_session.add(
        AccountIntegration(
            account_id=account_a.id,
            provider="bitrix",
            status="active",
            external_key="b24-a.bitrix24.ru",
            portal_id=portal_a.id,
        )
    )
    test_db_session.commit()
    _seed_plan(test_db_session, account_a.id, "start")

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    original_require_admin = bitrix_router._require_portal_admin
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    try:
        resp = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/web/link/precheck",
            json={"email": "owner@example.com", "password": "Secret123!"},
        )
    finally:
        bitrix_router._require_portal_admin = original_require_admin
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["attachable_accounts"][0]["attach_allowed"] is False
    assert data["attachable_accounts"][0]["reason"] == "bitrix_portal_limit_reached"
    assert data["attachable_accounts"][0]["bitrix_portals_limit"] == 1


@pytest.mark.timeout(10)
def test_bitrix_link_precheck_allows_attach_on_senior_plan(test_db_session):
    portal_b = Portal(domain="b24-b.bitrix24.ru", status="active", admin_user_id=1)
    portal_a = Portal(domain="b24-a.bitrix24.ru", status="active", admin_user_id=1)
    test_db_session.add_all([portal_a, portal_b])
    test_db_session.flush()

    web_user = WebUser(
        email="pro@example.com",
        password_hash=get_password_hash("Secret123!"),
        portal_id=portal_a.id,
        email_verified_at=datetime.utcnow(),
    )
    test_db_session.add(web_user)
    test_db_session.flush()

    app_user = AppUser(display_name="Pro Owner", status="active")
    test_db_session.add(app_user)
    test_db_session.flush()
    test_db_session.add(
        AppUserWebCredential(
            user_id=app_user.id,
            login="pro@example.com",
            email="pro@example.com",
            password_hash=get_password_hash("Secret123!"),
            email_verified_at=datetime.utcnow(),
        )
    )

    account_a = Account(name="Account A", status="active", account_no=100003, owner_user_id=app_user.id)
    test_db_session.add(account_a)
    test_db_session.flush()
    portal_a.account_id = account_a.id
    membership = AccountMembership(account_id=account_a.id, user_id=app_user.id, role="owner", status="active")
    test_db_session.add(membership)
    test_db_session.flush()
    test_db_session.add(
        AccountPermission(
            membership_id=membership.id,
            kb_access="write",
            can_invite_users=True,
            can_manage_settings=True,
            can_view_finance=True,
        )
    )
    test_db_session.add(
        AccountIntegration(
            account_id=account_a.id,
            provider="bitrix",
            status="active",
            external_key="b24-a.bitrix24.ru",
            portal_id=portal_a.id,
        )
    )
    test_db_session.commit()
    _seed_plan(test_db_session, account_a.id, "pro")

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    original_require_admin = bitrix_router._require_portal_admin
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    try:
        resp = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/web/link/precheck",
            json={"email": "pro@example.com", "password": "Secret123!"},
        )
    finally:
        bitrix_router._require_portal_admin = original_require_admin
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["recommended_action"] == "attach_existing"
    assert data["attachable_accounts"][0]["attach_allowed"] is True
    assert data["attachable_accounts"][0]["bitrix_portals_limit"] == 5


@pytest.mark.timeout(10)
def test_bitrix_create_account_action_creates_new_account_and_integration(test_db_session):
    portal_b = Portal(domain="b24-b.bitrix24.ru", status="active", admin_user_id=1)
    test_db_session.add(portal_b)
    test_db_session.flush()

    web_user = WebUser(
        email="newacc@example.com",
        password_hash=get_password_hash("Secret123!"),
        portal_id=None,
        email_verified_at=datetime.utcnow(),
    )
    test_db_session.add(web_user)
    test_db_session.flush()

    app_user = AppUser(display_name="Owner", status="active")
    test_db_session.add(app_user)
    test_db_session.flush()
    test_db_session.add(
        AppUserWebCredential(
            user_id=app_user.id,
            login="newacc@example.com",
            email="newacc@example.com",
            password_hash=get_password_hash("Secret123!"),
            email_verified_at=datetime.utcnow(),
        )
    )
    test_db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    original_require_admin = bitrix_router._require_portal_admin
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    try:
        resp = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/web/link/create-account",
            json={"email": "newacc@example.com", "password": "Secret123!", "account_name": "Account B"},
        )
    finally:
        bitrix_router._require_portal_admin = original_require_admin
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "linked"
    account = test_db_session.get(Account, int(data["account_id"]))
    assert account is not None
    assert account.name == "Account B"
    assert account.owner_user_id == app_user.id
    portal_b_db = test_db_session.get(Portal, portal_b.id)
    assert portal_b_db.account_id == account.id
    integ = test_db_session.query(AccountIntegration).filter(AccountIntegration.portal_id == portal_b.id).one()
    assert integ.account_id == account.id


@pytest.mark.timeout(10)
def test_bitrix_attach_existing_action_links_second_portal_without_detach(test_db_session):
    portal_a = Portal(domain="b24-a.bitrix24.ru", status="active", admin_user_id=1)
    portal_b = Portal(domain="b24-b.bitrix24.ru", status="active", admin_user_id=1)
    test_db_session.add_all([portal_a, portal_b])
    test_db_session.flush()

    web_user = WebUser(
        email="attach@example.com",
        password_hash=get_password_hash("Secret123!"),
        portal_id=portal_a.id,
        email_verified_at=datetime.utcnow(),
    )
    test_db_session.add(web_user)
    test_db_session.flush()

    app_user = AppUser(display_name="Owner", status="active")
    test_db_session.add(app_user)
    test_db_session.flush()
    test_db_session.add(
        AppUserWebCredential(
            user_id=app_user.id,
            login="attach@example.com",
            email="attach@example.com",
            password_hash=get_password_hash("Secret123!"),
            email_verified_at=datetime.utcnow(),
        )
    )

    account_a = Account(name="Account A", status="active", account_no=100004, owner_user_id=app_user.id)
    test_db_session.add(account_a)
    test_db_session.flush()
    portal_a.account_id = account_a.id
    membership = AccountMembership(account_id=account_a.id, user_id=app_user.id, role="owner", status="active")
    test_db_session.add(membership)
    test_db_session.flush()
    test_db_session.add(
        AccountPermission(
            membership_id=membership.id,
            kb_access="write",
            can_invite_users=True,
            can_manage_settings=True,
            can_view_finance=True,
        )
    )
    test_db_session.add(
        AccountIntegration(
            account_id=account_a.id,
            provider="bitrix",
            status="active",
            external_key="b24-a.bitrix24.ru",
            portal_id=portal_a.id,
        )
    )
    test_db_session.commit()
    _seed_plan(test_db_session, account_a.id, "pro")

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    original_require_admin = bitrix_router._require_portal_admin
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    try:
        resp = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/web/link/attach-existing",
            json={"email": "attach@example.com", "password": "Secret123!", "account_id": account_a.id},
        )
        status_resp = client.get(f"/v1/bitrix/portals/{portal_b.id}/web/status")
        login_resp = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/web/login",
            json={"email": "attach@example.com", "password": "Secret123!"},
        )
    finally:
        bitrix_router._require_portal_admin = original_require_admin
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert resp.status_code == 200
    assert resp.json()["action"] == "attach_existing"
    portal_b_db = test_db_session.get(Portal, portal_b.id)
    assert portal_b_db.account_id == account_a.id
    integrations = test_db_session.query(AccountIntegration).filter(AccountIntegration.account_id == account_a.id).all()
    assert sorted(i.external_key for i in integrations) == ["b24-a.bitrix24.ru", "b24-b.bitrix24.ru"]
    assert web_user.portal_id == portal_a.id
    assert status_resp.status_code == 200
    assert status_resp.json()["linked"] is True
    assert login_resp.status_code == 200
    assert login_resp.json()["status"] == "linked"


@pytest.mark.timeout(10)
def test_bitrix_embedded_session_returns_web_session_for_linked_account(test_db_session):
    portal_a = Portal(domain="b24-a.bitrix24.ru", status="active", admin_user_id=1)
    test_db_session.add(portal_a)
    test_db_session.flush()

    web_user = WebUser(
        email="embedded@example.com",
        password_hash=get_password_hash("Secret123!"),
        portal_id=portal_a.id,
        email_verified_at=datetime.utcnow(),
    )
    test_db_session.add(web_user)
    test_db_session.flush()

    app_user = AppUser(display_name="Owner", status="active")
    test_db_session.add(app_user)
    test_db_session.flush()
    test_db_session.add(
        AppUserWebCredential(
            user_id=app_user.id,
            login="embedded@example.com",
            email="embedded@example.com",
            password_hash=get_password_hash("Secret123!"),
            email_verified_at=datetime.utcnow(),
        )
    )

    account_a = Account(name="Account A", status="active", account_no=100005, owner_user_id=app_user.id)
    test_db_session.add(account_a)
    test_db_session.flush()
    portal_a.account_id = account_a.id
    membership = AccountMembership(account_id=account_a.id, user_id=app_user.id, role="owner", status="active")
    test_db_session.add(membership)
    test_db_session.flush()
    test_db_session.add(
        AccountPermission(
            membership_id=membership.id,
            kb_access="write",
            can_invite_users=True,
            can_manage_settings=True,
            can_view_finance=True,
        )
    )
    test_db_session.add(
        AccountIntegration(
            account_id=account_a.id,
            provider="bitrix",
            status="active",
            external_key="b24-a.bitrix24.ru",
            portal_id=portal_a.id,
        )
    )
    test_db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_a.id
    original_require_admin = bitrix_router._require_portal_admin
    original_create_portal_token = bitrix_router.create_portal_token_with_user
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    bitrix_router.create_portal_token_with_user = lambda portal_id, user_id=None, expires_minutes=60: "portal-token"
    try:
        resp = client.post(f"/v1/bitrix/portals/{portal_a.id}/web/embedded-session")
    finally:
        bitrix_router._require_portal_admin = original_require_admin
        bitrix_router.create_portal_token_with_user = original_create_portal_token
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["email"] == "embedded@example.com"
    assert data["active_account_id"] == account_a.id
    assert data["portal_id"] == portal_a.id
    assert data["session_token"]
    assert data["accounts"][0]["id"] == account_a.id


@pytest.mark.timeout(10)
def test_bitrix_login_returns_link_required_instead_of_legacy_pending(test_db_session):
    portal_a = Portal(domain="legacy-a.bitrix24.ru", status="active", admin_user_id=1)
    portal_b = Portal(domain="legacy-b.bitrix24.ru", status="active", admin_user_id=1)
    test_db_session.add_all([portal_a, portal_b])
    test_db_session.flush()

    web_user = WebUser(
        email="legacy@example.com",
        password_hash=get_password_hash("Secret123!"),
        portal_id=portal_a.id,
        email_verified_at=datetime.utcnow(),
    )
    test_db_session.add(web_user)
    test_db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    original_require_admin = bitrix_router._require_portal_admin
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    try:
        resp = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/web/login",
            json={"email": "legacy@example.com", "password": "Secret123!"},
        )
        legacy_resp = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/web/link/request",
            json={"email": "legacy@example.com"},
        )
    finally:
        bitrix_router._require_portal_admin = original_require_admin
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert resp.status_code == 200
    assert resp.json()["status"] == "link_required"
    assert legacy_resp.status_code == 410
    assert legacy_resp.json()["detail"] == "legacy_link_flow_removed"
