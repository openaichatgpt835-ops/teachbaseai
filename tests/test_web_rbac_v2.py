"""RBAC v2 web endpoints tests."""

from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from apps.backend.database import Base, get_test_engine
from apps.backend.deps import get_db
from apps.backend.routers import web_rbac_v2
from apps.backend.models.account import (
    Account,
    AccountInvite,
    AccountMembership,
    AccountPermission,
    AppUser,
    AppUserWebCredential,
)
from apps.backend.models.portal import Portal
from apps.backend.models.web_user import WebSession, WebUser

app = FastAPI()
app.include_router(web_rbac_v2.router, prefix="/v2/web")
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


def _seed_owner(db):
    account = Account(account_no=123001, name="Acme", status="active")
    db.add(account)
    db.flush()

    portal = Portal(domain="acme.bitrix24.ru", status="active", account_id=account.id)
    db.add(portal)
    db.flush()

    web_user = WebUser(
        email="owner@example.com",
        password_hash="hash",
        portal_id=portal.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(web_user)
    db.flush()

    app_user = AppUser(display_name="Owner", status="active")
    db.add(app_user)
    db.flush()

    cred = AppUserWebCredential(
        user_id=app_user.id,
        login="owner@example.com",
        email="owner@example.com",
        password_hash="hash",
        email_verified_at=datetime.utcnow(),
        must_change_password=False,
    )
    db.add(cred)
    db.flush()

    membership = AccountMembership(
        account_id=account.id,
        user_id=app_user.id,
        role="owner",
        status="active",
        invited_by_user_id=None,
    )
    db.add(membership)
    db.flush()

    perm = AccountPermission(
        membership_id=membership.id,
        kb_access="write",
        can_invite_users=True,
        can_manage_settings=True,
        can_view_finance=True,
    )
    db.add(perm)
    db.flush()

    account.owner_user_id = app_user.id
    db.add(account)

    session = WebSession(
        user_id=web_user.id,
        token="tok-owner",
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=1),
    )
    db.add(session)
    db.commit()
    return {
        "account_id": int(account.id),
        "owner_app_user_id": int(app_user.id),
        "token": session.token,
    }


@pytest.mark.timeout(10)
def test_web_rbac_me_and_list_users(test_db_session, override_get_db):
    seeded = _seed_owner(test_db_session)

    app.dependency_overrides[get_db] = override_get_db
    try:
        r_me = client.get(
            "/v2/web/auth/me",
            headers={"Authorization": f"Bearer {seeded['token']}"},
        )
        r_users = client.get(
            f"/v2/web/accounts/{seeded['account_id']}/users",
            headers={"Authorization": f"Bearer {seeded['token']}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r_me.status_code == 200
    me = r_me.json()
    assert me["account"]["id"] == seeded["account_id"]
    assert me["account"]["account_no"] == 123001

    assert r_users.status_code == 200
    items = r_users.json().get("items", [])
    assert len(items) == 1
    assert items[0]["role"] == "owner"
    assert items[0]["web"]["email"] == "owner@example.com"


@pytest.mark.timeout(10)
def test_web_rbac_manual_user_create_update_delete(test_db_session, override_get_db):
    seeded = _seed_owner(test_db_session)
    account_id = seeded["account_id"]

    app.dependency_overrides[get_db] = override_get_db
    try:
        r_create = client.post(
            f"/v2/web/accounts/{account_id}/users/manual",
            headers={"Authorization": f"Bearer {seeded['token']}"},
            json={
                "display_name": "Alice",
                "login": "alice",
                "email": "alice@example.com",
                "password": "alice-secret",
                "role": "member",
                "kb_access": "read",
            },
        )
        assert r_create.status_code == 200
        payload = r_create.json()
        user_id = int(payload["user_id"])
        membership_id = int(payload["membership_id"])

        r_update = client.patch(
            f"/v2/web/accounts/{account_id}/users/{user_id}",
            headers={"Authorization": f"Bearer {seeded['token']}"},
            json={
                "display_name": "Alice Admin",
                "role": "admin",
                "kb_access": "write",
                "can_manage_settings": True,
            },
        )
        assert r_update.status_code == 200

        r_perm = client.patch(
            f"/v2/web/accounts/{account_id}/memberships/{membership_id}/permissions",
            headers={"Authorization": f"Bearer {seeded['token']}"},
            json={
                "kb_access": "read",
                "can_manage_settings": False,
                "can_invite_users": False,
                "can_view_finance": True,
            },
        )
        assert r_perm.status_code == 200

        r_delete = client.delete(
            f"/v2/web/accounts/{account_id}/users/{user_id}",
            headers={"Authorization": f"Bearer {seeded['token']}"},
        )
        assert r_delete.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)

    membership = test_db_session.execute(
        select(AccountMembership).where(
            AccountMembership.account_id == account_id,
            AccountMembership.user_id == user_id,
        )
    ).scalar_one()
    assert membership.status == "deleted"

    perm = test_db_session.execute(
        select(AccountPermission).where(AccountPermission.membership_id == membership.id)
    ).scalar_one()
    assert perm.kb_access == "read"
    assert perm.can_manage_settings is False
    assert perm.can_invite_users is False
    assert perm.can_view_finance is True


@pytest.mark.timeout(10)
def test_web_rbac_owner_is_immutable_for_role_changes(test_db_session, override_get_db):
    seeded = _seed_owner(test_db_session)
    account_id = seeded["account_id"]
    owner_user_id = seeded["owner_app_user_id"]

    app.dependency_overrides[get_db] = override_get_db
    try:
        r = client.patch(
            f"/v2/web/accounts/{account_id}/users/{owner_user_id}",
            headers={"Authorization": f"Bearer {seeded['token']}"},
            json={"role": "admin"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 400
    assert r.json().get("detail") == "owner_immutable"


@pytest.mark.timeout(10)
def test_web_rbac_invite_accept_and_revoke(test_db_session, override_get_db):
    seeded = _seed_owner(test_db_session)
    account_id = seeded["account_id"]

    app.dependency_overrides[get_db] = override_get_db
    try:
        r_invite = client.post(
            f"/v2/web/accounts/{account_id}/invites/email",
            headers={"Authorization": f"Bearer {seeded['token']}"},
            json={
                "email": "bob@example.com",
                "role": "member",
                "kb_access": "read",
                "expires_days": 7,
            },
        )
        assert r_invite.status_code == 200
        invite = r_invite.json()
        accept_url = str(invite["accept_url"])
        token = parse_qs(urlparse(accept_url).query).get("token", [""])[0]
        assert token
        invite_id = int(invite["invite_id"])

        r_accept = client.post(
            f"/v2/web/invites/{token}/accept",
            json={
                "login": "bob",
                "password": "bob-secret",
                "display_name": "Bob",
            },
        )
        assert r_accept.status_code == 200
        accepted = r_accept.json()
        assert accepted["status"] == "ok"

        r_revoke_after_accept = client.post(
            f"/v2/web/accounts/{account_id}/invites/{invite_id}/revoke",
            headers={"Authorization": f"Bearer {seeded['token']}"},
        )
        assert r_revoke_after_accept.status_code == 400
        assert r_revoke_after_accept.json().get("detail") == "invite_already_accepted"

        r_invite2 = client.post(
            f"/v2/web/accounts/{account_id}/invites/email",
            headers={"Authorization": f"Bearer {seeded['token']}"},
            json={"email": "revokable@example.com", "role": "member", "expires_days": 7},
        )
        assert r_invite2.status_code == 200
        invite2_id = int(r_invite2.json()["invite_id"])
        r_revoke2 = client.post(
            f"/v2/web/accounts/{account_id}/invites/{invite2_id}/revoke",
            headers={"Authorization": f"Bearer {seeded['token']}"},
        )
        assert r_revoke2.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)

    inv_rows = test_db_session.execute(
        select(AccountInvite).where(AccountInvite.account_id == account_id).order_by(AccountInvite.id.asc())
    ).scalars().all()
    assert len(inv_rows) >= 2
    assert inv_rows[0].status == "accepted"
    assert inv_rows[1].status == "revoked"
    web_user = test_db_session.execute(
        select(WebUser).where(WebUser.email == "bob@example.com")
    ).scalar_one_or_none()
    assert web_user is not None
    assert int(web_user.portal_id or 0) > 0
    assert web_user.email_verified_at is not None
