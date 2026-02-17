"""GET /v1/bitrix/users returns normalized users list and handles missing scope."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from apps.backend.main import app
from apps.backend.deps import get_db
from apps.backend.database import get_test_engine, Base
from apps.backend.models.portal import Portal
from apps.backend.services.portal_tokens import save_tokens
from apps.backend.auth import create_portal_token_with_user

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
def test_bitrix_users_ok(test_db_session, override_get_db):
    portal = Portal(domain="test.bitrix24.ru", status="active")
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)

    save_tokens(test_db_session, portal.id, "access-1", "refresh-1", 3600)
    portal_token = create_portal_token_with_user(portal.id, user_id=1, expires_minutes=10)

    def fake_user_get(domain, access_token, start=0, limit=100):
        return ([{"ID": "10", "NAME": "Ivan", "LAST_NAME": "Petrov", "EMAIL": "ivan@example.com", "ACTIVE": True}], None)

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("apps.backend.routers.bitrix.user_get", side_effect=fake_user_get):
            r = client.get(
                f"/v1/bitrix/users?portal_id={portal.id}&limit=200",
                headers={"Authorization": f"Bearer {portal_token}"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    data = r.json()
    assert "users" in data
    assert data["total"] == 1
    assert data["users"][0]["id"] == "10"
    assert data["users"][0]["name"] == "Ivan"


@pytest.mark.timeout(10)
def test_bitrix_users_missing_scope_returns_403(test_db_session, override_get_db):
    portal = Portal(domain="test.bitrix24.ru", status="active")
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)

    save_tokens(test_db_session, portal.id, "access-2", "refresh-2", 3600)
    portal_token = create_portal_token_with_user(portal.id, user_id=1, expires_minutes=10)

    def fake_user_get(domain, access_token, start=0, limit=100):
        return ([], "missing_scope_user")

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("apps.backend.routers.bitrix.user_get", side_effect=fake_user_get):
            r = client.get(
                f"/v1/bitrix/users?portal_id={portal.id}&limit=200",
                headers={"Authorization": f"Bearer {portal_token}"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 403
    data = r.json()
    assert data.get("error") == "missing_scope_user"


@pytest.mark.timeout(10)
def test_bitrix_users_retry_after_refresh_succeeds(test_db_session, override_get_db):
    portal = Portal(domain="test.bitrix24.ru", status="active")
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)

    save_tokens(test_db_session, portal.id, "access-3", "refresh-3", 3600)
    portal_token = create_portal_token_with_user(portal.id, user_id=1, expires_minutes=10)

    calls = {"n": 0}

    def fake_user_get(domain, access_token, start=0, limit=100):
        calls["n"] += 1
        if calls["n"] == 1:
            return ([], "missing_scope_user")
        return ([{"ID": "11", "NAME": "Anna", "LAST_NAME": "Ivanova", "EMAIL": "anna@example.com", "ACTIVE": True}], None)

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("apps.backend.routers.bitrix.user_get", side_effect=fake_user_get), \
             patch("apps.backend.routers.bitrix.refresh_portal_tokens", return_value={"ok": True}):
            r = client.get(
                f"/v1/bitrix/users?portal_id={portal.id}&limit=200",
                headers={"Authorization": f"Bearer {portal_token}"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["users"][0]["id"] == "11"
