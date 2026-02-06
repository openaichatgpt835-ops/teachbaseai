"""Admin bot actions auto-refresh auth flow."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from apps.backend.main import app
from apps.backend.deps import get_db
from apps.backend.database import get_test_engine, Base
from apps.backend.models.portal import Portal, PortalToken
from apps.backend.auth import create_access_token
from apps.backend.services.token_crypto import encrypt_token
from apps.backend.clients import bitrix as bitrix_client

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


@pytest.mark.timeout(15)
def test_bot_check_refresh_retry(monkeypatch, test_db_session, override_get_db):
    stub_settings = type("S", (), {
        "token_encryption_key": "x" * 32,
        "secret_key": "y" * 32,
        "bitrix_client_id": "",
        "bitrix_client_secret": "",
    })()
    monkeypatch.setattr("apps.backend.services.portal_tokens.get_settings", lambda: stub_settings)

    portal = Portal(domain="example.invalid", status="active")
    portal.local_client_id = "local.app"
    portal.local_client_secret_encrypted = encrypt_token("secret", stub_settings.token_encryption_key)
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)

    row = PortalToken(portal_id=portal.id, access_token=encrypt_token("old", stub_settings.token_encryption_key), refresh_token=encrypt_token("r1", stub_settings.token_encryption_key))
    test_db_session.add(row)
    test_db_session.commit()

    calls = {"count": 0}

    def fake_rest_call(domain, access_token, method, params, timeout_sec=30):
        calls["count"] += 1
        if calls["count"] == 1:
            return None, bitrix_client.BITRIX_ERR_AUTH_INVALID, "expired", 401
        return {"result": []}, None, "", 200

    def fake_refresh(domain, refresh_token_val, client_id, client_secret):
        return {"access_token": "new", "refresh_token": "r2", "expires_in": 3600}, 200, ""

    monkeypatch.setattr(bitrix_client, "rest_call_result_detailed", fake_rest_call)
    monkeypatch.setattr(bitrix_client, "refresh_token", fake_refresh)

    app.dependency_overrides[get_db] = override_get_db
    try:
        admin_token = create_access_token({"sub": "admin"})
        r = client.post(
            f"/v1/admin/portals/{portal.id}/bot/check",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    data = r.json()
    assert data.get("status") in ("ok", "error")
    assert calls["count"] == 2
