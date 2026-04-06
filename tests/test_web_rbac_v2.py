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
    AccountIntegration,
    AccountInvite,
    AccountMembership,
    AccountPermission,
    AccountUserGroup,
    AccountUserGroupMember,
    AppSession,
    AppUser,
    AppUserIdentity,
    AppUserWebCredential,
)
from apps.backend.models.portal import Portal, PortalUsersAccess
from apps.backend.models.web_user import WebSession, WebUser
from apps.backend.models.billing import AccountSubscription, BillingPlan, BillingUsage
from apps.backend.services.billing import ensure_base_plans, is_limit_exceeded

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
        kb_access="manage",
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
        app_user_id=app_user.id,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=1),
    )
    db.add(session)
    db.add(
        AppSession(
            user_id=app_user.id,
            active_account_id=account.id,
            token=session.token,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=1),
        )
    )
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
def test_web_rbac_permissions_schema_includes_client_role(test_db_session, override_get_db):
    seeded = _seed_owner(test_db_session)

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get(
            f"/v2/web/accounts/{seeded['account_id']}/permissions/schema",
            headers={"Authorization": f"Bearer {seeded['token']}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert "client" in payload["role"]


@pytest.mark.timeout(10)
def test_web_rbac_access_center_merges_bitrix_allowlist_status(test_db_session, override_get_db):
    seeded = _seed_owner(test_db_session)
    account_id = seeded["account_id"]

    app_user = test_db_session.execute(
        select(AppUser).where(AppUser.display_name == "Owner")
    ).scalar_one()
    test_db_session.add(
        AppUserIdentity(
            user_id=app_user.id,
            provider="bitrix",
            integration_id=None,
            external_id="42",
            display_value="Битрикс Owner",
            created_at=datetime.utcnow(),
        )
    )
    portal = test_db_session.execute(select(Portal).where(Portal.account_id == account_id)).scalar_one()
    test_db_session.add(
        PortalUsersAccess(
            portal_id=portal.id,
            user_id="42",
            display_name="Битрикс Owner",
            telegram_username="owner_tg",
            kind="bitrix",
        )
    )
    test_db_session.add(
        PortalUsersAccess(
            portal_id=portal.id,
            user_id="webu_test",
            display_name="Legacy TG User",
            telegram_username="legacy_support",
            kind="web",
        )
    )
    test_db_session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        r_access = client.get(
            f"/v2/web/accounts/{account_id}/access-center",
            headers={"Authorization": f"Bearer {seeded['token']}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r_access.status_code == 200, r_access.text
    payload = r_access.json()
    assert payload["portal_id"] == portal.id
    assert len(payload["legacy_web_users"]) == 1
    item = payload["items"][0]
    assert item["access_center"]["bitrix_linked"] is True
    assert item["access_center"]["bitrix_allowlist"] is True
    assert item["access_center"]["telegram_username"] == "owner_tg"


@pytest.mark.timeout(10)
def test_web_rbac_access_center_filters_identities_to_current_account(test_db_session, override_get_db):
    seeded = _seed_owner(test_db_session)
    account_id = seeded["account_id"]
    owner_user = test_db_session.execute(select(AppUser).where(AppUser.display_name == "Owner")).scalar_one()
    current_portal = test_db_session.execute(select(Portal).where(Portal.account_id == account_id)).scalar_one()

    current_integration = AccountIntegration(
        account_id=account_id,
        provider="bitrix",
        status="active",
        external_key="current-portal",
        portal_id=current_portal.id,
    )
    test_db_session.add(current_integration)
    test_db_session.flush()

    other_account = Account(account_no=123002, name="Other", status="active")
    test_db_session.add(other_account)
    test_db_session.flush()
    other_portal = Portal(domain="other.bitrix24.ru", status="active", account_id=other_account.id)
    test_db_session.add(other_portal)
    test_db_session.flush()
    other_integration = AccountIntegration(
        account_id=other_account.id,
        provider="bitrix",
        status="active",
        external_key="other-portal",
        portal_id=other_portal.id,
    )
    test_db_session.add(other_integration)
    test_db_session.flush()

    test_db_session.add_all(
        [
            AppUserIdentity(
                user_id=owner_user.id,
                provider="bitrix",
                integration_id=current_integration.id,
                external_id="42",
                display_value="Current Bitrix",
                created_at=datetime.utcnow(),
            ),
            AppUserIdentity(
                user_id=owner_user.id,
                provider="bitrix",
                integration_id=other_integration.id,
                external_id="77",
                display_value="Other Bitrix",
                created_at=datetime.utcnow(),
            ),
        ]
    )
    test_db_session.add(
        PortalUsersAccess(
            portal_id=current_portal.id,
            user_id="42",
            display_name="Current Bitrix",
            telegram_username="owner_tg",
            kind="bitrix",
        )
    )
    test_db_session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get(
            f"/v2/web/accounts/{account_id}/access-center",
            headers={"Authorization": f"Bearer {seeded['token']}"},
        )
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert [x["external_id"] for x in item["bitrix"]] == ["42"]
        assert item["access_center"]["telegram_username"] == "owner_tg"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_web_rbac_membership_telegram_identity_patch(test_db_session, override_get_db):
    seeded = _seed_owner(test_db_session)
    account_id = seeded["account_id"]
    token = seeded["token"]

    user = AppUser(display_name="Client Tg", status="active")
    test_db_session.add(user)
    test_db_session.flush()
    membership = AccountMembership(account_id=account_id, user_id=user.id, role="client", status="active")
    test_db_session.add(membership)
    test_db_session.flush()
    test_db_session.add(
        AccountPermission(
            membership_id=membership.id,
            kb_access="none",
            can_invite_users=False,
            can_manage_settings=False,
            can_view_finance=False,
        )
    )
    test_db_session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        save_resp = client.patch(
            f"/v2/web/accounts/{account_id}/memberships/{membership.id}/telegram",
            headers={"Authorization": f"Bearer {token}"},
            json={"telegram_username": "@client_acme"},
        )
        assert save_resp.status_code == 200, save_resp.text

        access_resp = client.get(
            f"/v2/web/accounts/{account_id}/access-center",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert access_resp.status_code == 200
        items = access_resp.json()["items"]
        item = next(x for x in items if int(x["membership_id"]) == int(membership.id))
        assert item["telegram"][0]["external_id"] == "client_acme"

        clear_resp = client.patch(
            f"/v2/web/accounts/{account_id}/memberships/{membership.id}/telegram",
            headers={"Authorization": f"Bearer {token}"},
            json={"telegram_username": ""},
        )
        assert clear_resp.status_code == 200

        access_resp = client.get(
            f"/v2/web/accounts/{account_id}/access-center",
            headers={"Authorization": f"Bearer {token}"},
        )
        item = next(x for x in access_resp.json()["items"] if int(x["membership_id"]) == int(membership.id))
        assert item["telegram"] == []
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.timeout(10)
def test_web_rbac_user_groups_crud(test_db_session, override_get_db):
    seeded = _seed_owner(test_db_session)
    account_id = seeded["account_id"]

    member_user = AppUser(display_name="Member", status="active")
    test_db_session.add(member_user)
    test_db_session.flush()
    member_membership = AccountMembership(
        account_id=account_id,
        user_id=member_user.id,
        role="member",
        status="active",
        invited_by_user_id=seeded["owner_app_user_id"],
    )
    test_db_session.add(member_membership)
    test_db_session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        create_resp = client.post(
            f"/v2/web/accounts/{account_id}/user-groups",
            headers={"Authorization": f"Bearer {seeded['token']}"},
            json={"name": "Sales", "kind": "staff", "membership_ids": [member_membership.id]},
        )
        assert create_resp.status_code == 200, create_resp.text
        group = create_resp.json()["group"]
        assert group["name"] == "Sales"
        assert group["kind"] == "staff"
        assert group["membership_ids"] == [member_membership.id]
        group_id = int(group["id"])

        list_resp = client.get(
            f"/v2/web/accounts/{account_id}/user-groups",
            headers={"Authorization": f"Bearer {seeded['token']}"},
        )
        assert list_resp.status_code == 200, list_resp.text
        items = list_resp.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == group_id

        access_resp = client.get(
            f"/v2/web/accounts/{account_id}/access-center",
            headers={"Authorization": f"Bearer {seeded['token']}"},
        )
        assert access_resp.status_code == 200, access_resp.text
        payload = access_resp.json()
        assert len(payload["groups"]) == 1
        member_item = next(item for item in payload["items"] if item["membership_id"] == member_membership.id)
        assert member_item["groups"] == [{"id": group_id, "name": "Sales", "kind": "staff"}]

        update_resp = client.patch(
            f"/v2/web/accounts/{account_id}/user-groups/{group_id}",
            headers={"Authorization": f"Bearer {seeded['token']}"},
            json={"name": "Shared", "kind": "staff", "membership_ids": []},
        )
        assert update_resp.status_code == 200, update_resp.text
        updated = update_resp.json()["group"]
        assert updated["name"] == "Shared"
        assert updated["kind"] == "staff"
        assert updated["membership_ids"] == []

        delete_resp = client.delete(
            f"/v2/web/accounts/{account_id}/user-groups/{group_id}",
            headers={"Authorization": f"Bearer {seeded['token']}"},
        )
        assert delete_resp.status_code == 200, delete_resp.text
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert test_db_session.execute(select(AccountUserGroup)).scalars().all() == []
    assert test_db_session.execute(select(AccountUserGroupMember)).scalars().all() == []


@pytest.mark.timeout(10)
def test_web_rbac_client_groups_only_accept_client_memberships(test_db_session, override_get_db):
    seeded = _seed_owner(test_db_session)
    account_id = seeded["account_id"]

    client_user = AppUser(display_name="Client User", status="active")
    member_user = AppUser(display_name="Staff User", status="active")
    test_db_session.add_all([client_user, member_user])
    test_db_session.flush()
    client_membership = AccountMembership(
        account_id=account_id,
        user_id=client_user.id,
        role="client",
        status="active",
        invited_by_user_id=seeded["owner_app_user_id"],
    )
    member_membership = AccountMembership(
        account_id=account_id,
        user_id=member_user.id,
        role="member",
        status="active",
        invited_by_user_id=seeded["owner_app_user_id"],
    )
    test_db_session.add_all([client_membership, member_membership])
    test_db_session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        ok_resp = client.post(
            f"/v2/web/accounts/{account_id}/user-groups",
            headers={"Authorization": f"Bearer {seeded['token']}"},
            json={"name": "Acme Clients", "kind": "client", "membership_ids": [client_membership.id]},
        )
        bad_resp = client.post(
            f"/v2/web/accounts/{account_id}/user-groups",
            headers={"Authorization": f"Bearer {seeded['token']}"},
            json={"name": "Broken Clients", "kind": "client", "membership_ids": [member_membership.id]},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert ok_resp.status_code == 200, ok_resp.text
    assert ok_resp.json()["group"]["kind"] == "client"
    assert bad_resp.status_code == 400
    assert bad_resp.json()["detail"] == "group_members_kind_mismatch"


@pytest.mark.timeout(10)
def test_web_rbac_bitrix_integrations_list_make_primary_and_disconnect(test_db_session, override_get_db):
    seeded = _seed_owner(test_db_session)
    account_id = seeded["account_id"]
    portal_a = test_db_session.execute(select(Portal).where(Portal.account_id == account_id)).scalar_one()
    portal_b = Portal(domain="second.bitrix24.ru", status="active", account_id=account_id)
    test_db_session.add(portal_b)
    test_db_session.flush()
    integ_a = AccountIntegration(
        account_id=account_id,
        provider="bitrix",
        status="active",
        external_key="acme.bitrix24.ru",
        portal_id=portal_a.id,
        credentials_json={"is_primary": True},
    )
    integ_b = AccountIntegration(
        account_id=account_id,
        provider="bitrix",
        status="active",
        external_key="second.bitrix24.ru",
        portal_id=portal_b.id,
        credentials_json={},
    )
    test_db_session.add_all([integ_a, integ_b])
    test_db_session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        listed = client.get(
            f"/v2/web/accounts/{account_id}/integrations/bitrix",
            headers={"Authorization": f"Bearer {seeded['token']}"},
        )
        make_primary = client.post(
            f"/v2/web/accounts/{account_id}/integrations/bitrix/{integ_b.id}/make-primary",
            headers={"Authorization": f"Bearer {seeded['token']}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert listed.status_code == 200, listed.text
    assert len(listed.json()["items"]) == 2
    assert any(item["is_primary"] for item in listed.json()["items"])

    assert make_primary.status_code == 200, make_primary.text
    items = make_primary.json()["items"]
    primary = next(item for item in items if item["id"] == integ_b.id)
    assert primary["is_primary"] is True

    test_db_session.expire_all()
    owner_web = test_db_session.execute(select(WebUser).where(WebUser.email == "owner@example.com")).scalar_one()
    assert owner_web.portal_id == portal_b.id

    app.dependency_overrides[get_db] = override_get_db
    try:
        disconnect = client.delete(
            f"/v2/web/accounts/{account_id}/integrations/bitrix/{integ_b.id}",
            headers={"Authorization": f"Bearer {seeded['token']}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert disconnect.status_code == 200, disconnect.text
    items = disconnect.json()["items"]
    deleted = next(item for item in items if item["id"] == integ_b.id)
    survivor = next(item for item in items if item["id"] == integ_a.id)
    assert deleted["status"] == "deleted"
    assert survivor["is_primary"] is True

    test_db_session.expire_all()
    owner_web = test_db_session.execute(select(WebUser).where(WebUser.email == "owner@example.com")).scalar_one()
    assert owner_web.portal_id == portal_a.id
    portal_b_db = test_db_session.get(Portal, portal_b.id)
    assert portal_b_db.account_id is None


@pytest.mark.timeout(10)
def test_web_rbac_billing_endpoints(test_db_session, override_get_db):
    seeded = _seed_owner(test_db_session)
    account_id = seeded["account_id"]
    ensure_base_plans(test_db_session)
    business_plan = test_db_session.execute(select(BillingPlan).where(BillingPlan.code == "business")).scalar_one()
    test_db_session.add(
        AccountSubscription(
            account_id=account_id,
            plan_id=business_plan.id,
            status="active",
            started_at=datetime.utcnow(),
        )
    )
    portal = test_db_session.execute(select(Portal).where(Portal.account_id == account_id)).scalar_one()
    test_db_session.add(
        BillingUsage(
            portal_id=portal.id,
            kind="chat",
            status="ok",
            tokens_total=321,
            cost_rub=1.23,
            created_at=datetime.utcnow(),
        )
    )
    test_db_session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        plans_resp = client.get(
            "/v2/web/billing/plans",
            headers={"Authorization": f"Bearer {seeded['token']}"},
        )
        billing_resp = client.get(
            f"/v2/web/accounts/{account_id}/billing",
            headers={"Authorization": f"Bearer {seeded['token']}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert plans_resp.status_code == 200, plans_resp.text
    assert billing_resp.status_code == 200, billing_resp.text
    plan_codes = [item["code"] for item in plans_resp.json()["items"]]
    assert plan_codes == ["start", "business", "pro"]
    payload = billing_resp.json()
    assert payload["account"]["id"] == account_id
    assert payload["subscription"]["plan"]["code"] == "business"
    assert payload["effective_policy"]["plan_code"] == "business"
    assert payload["usage"]["requests_used"] == 1
    assert payload["usage"]["requests_limit"] == 10000
    assert payload["usage"]["tokens_total"] == 321


@pytest.mark.timeout(10)
def test_is_limit_exceeded_uses_account_plan_when_portal_override_missing(test_db_session, override_get_db):
    seeded = _seed_owner(test_db_session)
    account_id = seeded["account_id"]
    ensure_base_plans(test_db_session)
    start_plan = test_db_session.execute(select(BillingPlan).where(BillingPlan.code == "start")).scalar_one()
    test_db_session.add(
        AccountSubscription(
            account_id=account_id,
            plan_id=start_plan.id,
            status="active",
            started_at=datetime.utcnow(),
        )
    )
    portal = test_db_session.execute(select(Portal).where(Portal.account_id == account_id)).scalar_one()
    test_db_session.add_all(
        [
            BillingUsage(
                portal_id=portal.id,
                kind="chat",
                status="ok",
                created_at=datetime.utcnow(),
            )
            for _ in range(3000)
        ]
    )
    test_db_session.commit()

    assert is_limit_exceeded(test_db_session, int(portal.id)) is True


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
                "kb_access": "manage",
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
def test_web_rbac_manual_user_can_be_created_as_client(test_db_session, override_get_db):
    seeded = _seed_owner(test_db_session)
    account_id = seeded["account_id"]

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            f"/v2/web/accounts/{account_id}/users/manual",
            headers={"Authorization": f"Bearer {seeded['token']}"},
            json={
                "display_name": "Client User",
                "login": "client-user",
                "email": "client@example.com",
                "password": "client-secret",
                "role": "client",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200, response.text
    payload = response.json()
    membership = test_db_session.execute(
        select(AccountMembership).where(AccountMembership.id == int(payload["membership_id"]))
    ).scalar_one()
    perm = test_db_session.execute(
        select(AccountPermission).where(AccountPermission.membership_id == int(membership.id))
    ).scalar_one()
    assert membership.role == "client"
    assert perm.kb_access == "none"
    assert perm.can_invite_users is False
    assert perm.can_manage_settings is False
    assert perm.can_view_finance is False


@pytest.mark.timeout(10)
def test_web_rbac_manual_user_respects_max_users_limit(test_db_session, override_get_db):
    seeded = _seed_owner(test_db_session)
    account_id = seeded["account_id"]
    ensure_base_plans(test_db_session)
    start_plan = test_db_session.execute(select(BillingPlan).where(BillingPlan.code == "start")).scalar_one()
    test_db_session.add(
        AccountSubscription(
            account_id=account_id,
            plan_id=start_plan.id,
            status="active",
            started_at=datetime.utcnow(),
        )
    )
    for idx in range(4):
        app_user = AppUser(display_name=f"Member {idx}", status="active")
        test_db_session.add(app_user)
        test_db_session.flush()
        test_db_session.add(
            AccountMembership(
                account_id=account_id,
                user_id=app_user.id,
                role="member",
                status="active",
                invited_by_user_id=seeded["owner_app_user_id"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
    test_db_session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        r_create = client.post(
            f"/v2/web/accounts/{account_id}/users/manual",
            headers={"Authorization": f"Bearer {seeded['token']}"},
            json={
                "display_name": "Overflow",
                "login": "overflow",
                "email": "overflow@example.com",
                "password": "overflow-secret",
                "role": "member",
                "kb_access": "read",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r_create.status_code == 403
    assert r_create.json().get("detail") == "max_users_limit_reached"


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


@pytest.mark.timeout(10)
def test_web_rbac_client_invite_accepts_with_client_defaults(test_db_session, override_get_db):
    seeded = _seed_owner(test_db_session)
    account_id = seeded["account_id"]

    app.dependency_overrides[get_db] = override_get_db
    try:
        invite_response = client.post(
            f"/v2/web/accounts/{account_id}/invites/email",
            headers={"Authorization": f"Bearer {seeded['token']}"},
            json={
                "email": "client-invite@example.com",
                "role": "client",
                "expires_days": 7,
            },
        )
        assert invite_response.status_code == 200, invite_response.text
        invite_payload = invite_response.json()
        token = parse_qs(urlparse(str(invite_payload["accept_url"])).query).get("token", [""])[0]
        assert token

        accept_response = client.post(
            f"/v2/web/invites/{token}/accept",
            json={
                "login": "client-invite",
                "password": "client-secret",
                "display_name": "Client Invite",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert accept_response.status_code == 200, accept_response.text
    payload = accept_response.json()
    membership = test_db_session.execute(
        select(AccountMembership).where(AccountMembership.id == int(payload["membership_id"]))
    ).scalar_one()
    perm = test_db_session.execute(
        select(AccountPermission).where(AccountPermission.membership_id == int(membership.id))
    ).scalar_one()
    assert membership.role == "client"
    assert perm.kb_access == "none"
    assert perm.can_invite_users is False
    assert perm.can_manage_settings is False
    assert perm.can_view_finance is False
