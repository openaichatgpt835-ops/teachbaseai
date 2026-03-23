from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from apps.backend.auth import get_password_hash
from apps.backend.database import Base, get_test_engine
from apps.backend.deps import get_db
from apps.backend.models.account import Account, AccountMembership, AppSession, AppUser, AppUserWebCredential
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


def _seed_multi_account_user(db):
    app_user = AppUser(display_name="Alex", status="active")
    db.add(app_user)
    db.flush()

    cred = AppUserWebCredential(
        user_id=app_user.id,
        login="alex@example.com",
        email="alex@example.com",
        password_hash=get_password_hash("secret-123"),
        email_verified_at=datetime.utcnow(),
    )
    db.add(cred)

    acc1 = Account(account_no=100101, name="Necrogame / KB", slug="necrogame-kb", status="active", owner_user_id=app_user.id)
    acc2 = Account(account_no=100102, name="Necrogame / AI ROP", slug="necrogame-ai-rop", status="active", owner_user_id=app_user.id)
    db.add_all([acc1, acc2])
    db.flush()

    db.add_all(
        [
            AccountMembership(account_id=acc1.id, user_id=app_user.id, role="owner", status="active"),
            AccountMembership(account_id=acc2.id, user_id=app_user.id, role="owner", status="active"),
        ]
    )

    p1 = Portal(domain="web:kb", status="active", install_type="web", account_id=acc1.id)
    p2 = Portal(domain="web:ai-rop", status="active", install_type="web", account_id=acc2.id)
    db.add_all([p1, p2])
    db.flush()

    web_user = WebUser(
        email="alex@example.com",
        password_hash=cred.password_hash,
        portal_id=p1.id,
        email_verified_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(web_user)
    db.commit()
    return {
        "app_user_id": app_user.id,
        "account1_id": acc1.id,
        "account2_id": acc2.id,
        "portal1_id": p1.id,
        "portal2_id": p2.id,
        "web_user_id": web_user.id,
    }


@pytest.mark.timeout(10)
def test_login_me_and_switch_account_multi_membership_flow(test_db_session, override_get_db):
    ids = _seed_multi_account_user(test_db_session)
    app.dependency_overrides[get_db] = override_get_db
    try:
        login = client.post(
            "/v1/web/auth/login",
            json={"email": "alex@example.com", "password": "secret-123"},
        )
        assert login.status_code == 200, login.text
        payload = login.json()
        assert payload["active_account_id"] == ids["account1_id"]
        assert payload["portal_id"] == ids["portal1_id"]
        assert len(payload["accounts"]) == 2
        token = payload["session_token"]

        web_session = test_db_session.execute(
            select(WebSession).where(WebSession.token == token)
        ).scalar_one()
        assert web_session.app_user_id == ids["app_user_id"]

        app_session = test_db_session.execute(
            select(AppSession).where(AppSession.token == token)
        ).scalar_one()
        assert app_session.user_id == ids["app_user_id"]
        assert app_session.active_account_id == ids["account1_id"]

        me = client.get(
            "/v1/web/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me.status_code == 200, me.text
        me_payload = me.json()
        assert me_payload["session_token"] == token
        assert me_payload["active_account_id"] == ids["account1_id"]
        assert len(me_payload["accounts"]) == 2

        switched = client.post(
            "/v1/web/auth/switch-account",
            json={"account_id": ids["account2_id"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert switched.status_code == 200, switched.text
        switched_payload = switched.json()
        assert switched_payload["active_account_id"] == ids["account2_id"]
        assert switched_payload["portal_id"] == ids["portal2_id"]

        test_db_session.expire_all()
        app_session = test_db_session.execute(
            select(AppSession).where(AppSession.token == token)
        ).scalar_one()
        assert app_session.active_account_id == ids["account2_id"]

        web_user = test_db_session.get(WebUser, ids["web_user_id"])
        assert web_user.portal_id == ids["portal2_id"]
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.timeout(10)
def test_switch_account_forbidden_without_membership(test_db_session, override_get_db):
    ids = _seed_multi_account_user(test_db_session)
    outsider = Account(account_no=100103, name="Other / Secret", slug="other-secret", status="active")
    test_db_session.add(outsider)
    test_db_session.flush()
    test_db_session.add(Portal(domain="web:other", status="active", install_type="web", account_id=outsider.id))
    test_db_session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        login = client.post(
            "/v1/web/auth/login",
            json={"email": "alex@example.com", "password": "secret-123"},
        )
        token = login.json()["session_token"]
        switched = client.post(
            "/v1/web/auth/switch-account",
            json={"account_id": outsider.id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert switched.status_code == 403
        assert switched.json()["detail"] == "forbidden"
    finally:
        app.dependency_overrides.pop(get_db, None)
