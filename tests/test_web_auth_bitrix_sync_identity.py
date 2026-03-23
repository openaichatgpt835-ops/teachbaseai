from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from apps.backend.database import Base, get_test_engine
from apps.backend.deps import get_db
from apps.backend.models.account import Account, AccountMembership, AppUser, AppUserIdentity, AppUserWebCredential
from apps.backend.models.portal import Portal
from apps.backend.models.web_user import WebSession, WebUser
from apps.backend.routers import web_auth


app = FastAPI()
app.include_router(web_auth.router, prefix="/v1/web")
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


def _seed_owner_portal(db):
    owner = AppUser(display_name="Owner", status="active")
    db.add(owner)
    db.flush()
    account = Account(
        account_no=110001,
        name="Acme / Main",
        slug="acme-main",
        status="active",
        owner_user_id=owner.id,
    )
    db.add(account)
    db.flush()
    portal = Portal(
        domain="acme.bitrix24.ru",
        status="active",
        install_type="market",
        account_id=account.id,
    )
    db.add(portal)
    db.flush()
    db.add(
        AppUserWebCredential(
            user_id=owner.id,
            login="owner@example.com",
            email="owner@example.com",
            password_hash="hash",
            email_verified_at=datetime.utcnow(),
        )
    )
    db.add(AccountMembership(account_id=account.id, user_id=owner.id, role="owner", status="active"))
    web_user = WebUser(
        email="owner@example.com",
        password_hash="hash",
        portal_id=portal.id,
        email_verified_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(web_user)
    db.flush()
    db.add(
        WebSession(
            user_id=web_user.id,
            app_user_id=owner.id,
            token="tok-owner",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=1),
        )
    )
    db.commit()
    return account, portal


def _seed_existing_global_user(db):
    user = AppUser(display_name="Shared User", status="active")
    db.add(user)
    db.flush()
    other_account = Account(
        account_no=110002,
        name="Other / Workspace",
        slug="other-workspace",
        status="active",
    )
    db.add(other_account)
    db.flush()
    db.add(
        AppUserWebCredential(
            user_id=user.id,
            login="shared@example.com",
            email="shared@example.com",
            password_hash="hash",
            email_verified_at=datetime.utcnow(),
        )
    )
    db.add(AccountMembership(account_id=other_account.id, user_id=user.id, role="member", status="active"))
    db.commit()
    return user


@pytest.mark.timeout(10)
def test_sync_bitrix_users_links_existing_email_across_accounts_and_creates_membership(
    test_db_session,
    override_get_db,
    monkeypatch,
):
    account, portal = _seed_owner_portal(test_db_session)
    existing_user = _seed_existing_global_user(test_db_session)

    monkeypatch.setattr(web_auth, "get_valid_access_token", lambda db, portal_id: "bitrix-token")
    monkeypatch.setattr(
        web_auth,
        "user_get",
        lambda domain_full, access_token, start=0, limit=200: (
            [
                {
                    "ID": "42",
                    "EMAIL": "shared@example.com",
                    "NAME": "Shared",
                    "LAST_NAME": "User",
                }
            ],
            None,
        ),
    )

    app.dependency_overrides[get_db] = override_get_db
    try:
        res = client.post(
            f"/v1/web/portals/{portal.id}/bitrix/users/sync",
            headers={"Authorization": "Bearer tok-owner"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["identity_linking"]["linked"] == 1
    assert payload["identity_linking"]["memberships_created"] == 1

    ident = test_db_session.execute(
        select(AppUserIdentity).where(
            AppUserIdentity.provider == "bitrix",
            AppUserIdentity.external_id == "42",
        )
    ).scalar_one()
    assert ident.user_id == existing_user.id

    membership = test_db_session.execute(
        select(AccountMembership).where(
            AccountMembership.account_id == account.id,
            AccountMembership.user_id == existing_user.id,
        )
    ).scalar_one()
    assert membership.role == "member"
