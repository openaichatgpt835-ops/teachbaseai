from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from apps.backend.auth import get_password_hash, verify_password
from apps.backend.database import Base, get_test_engine
from apps.backend.deps import get_db
from apps.backend.models.account import AppUser, AppUserWebCredential
from apps.backend.models.portal import Portal
from apps.backend.models.web_user import WebEmailToken, WebSession, WebUser
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


def _seed_user(db):
    portal = Portal(domain="web:test-reset", status="active", install_type="web")
    db.add(portal)
    db.flush()

    user = WebUser(
        email="reset@example.com",
        password_hash=get_password_hash("old-password"),
        portal_id=portal.id,
        email_verified_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(user)
    db.flush()

    app_user = AppUser(display_name="Reset User", status="active")
    db.add(app_user)
    db.flush()

    cred = AppUserWebCredential(
        user_id=app_user.id,
        login="reset_user",
        email=user.email,
        password_hash=user.password_hash,
        email_verified_at=datetime.utcnow(),
        must_change_password=True,
    )
    db.add(cred)

    session = WebSession(
        user_id=user.id,
        token="sess-reset",
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=5),
    )
    db.add(session)
    db.commit()
    return user


@pytest.mark.timeout(10)
def test_password_reset_flow_updates_password_and_kills_sessions(monkeypatch, test_db_session, override_get_db):
    user = _seed_user(test_db_session)

    def _fake_send_email(**kwargs):
        return True, None

    monkeypatch.setattr("apps.backend.services.web_email.send_email", _fake_send_email)

    app.dependency_overrides[get_db] = override_get_db
    try:
        r_forgot = client.post("/v1/web/auth/password/forgot", json={"email": "reset@example.com"})
        assert r_forgot.status_code == 200

        rec = test_db_session.execute(
            select(WebEmailToken).where(
                WebEmailToken.user_id == user.id,
                WebEmailToken.kind == "reset_password",
                WebEmailToken.used_at.is_(None),
            )
        ).scalar_one_or_none()
        assert rec is not None

        r_reset = client.post(
            "/v1/web/auth/password/reset",
            json={"token": rec.token, "password": "new-password"},
        )
        assert r_reset.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)

    user_after = test_db_session.get(WebUser, user.id)
    assert user_after is not None
    assert verify_password("new-password", user_after.password_hash)

    rec_after = test_db_session.get(WebEmailToken, rec.id)
    assert rec_after is not None
    assert rec_after.used_at is not None

    sessions = test_db_session.execute(
        select(WebSession).where(WebSession.user_id == user.id)
    ).scalars().all()
    assert sessions == []

    cred = test_db_session.execute(
        select(AppUserWebCredential).where(AppUserWebCredential.email == "reset@example.com")
    ).scalar_one_or_none()
    assert cred is not None
    assert verify_password("new-password", cred.password_hash)
    assert cred.must_change_password is False


@pytest.mark.timeout(10)
def test_password_reset_invalid_token(monkeypatch, test_db_session, override_get_db):
    _seed_user(test_db_session)

    def _fake_send_email(**kwargs):
        return True, None

    monkeypatch.setattr("apps.backend.services.web_email.send_email", _fake_send_email)

    app.dependency_overrides[get_db] = override_get_db
    try:
        r_reset = client.post(
            "/v1/web/auth/password/reset",
            json={"token": "bad-token", "password": "new-password"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r_reset.status_code == 400
    assert r_reset.json().get("detail") == "invalid_or_expired_token"
