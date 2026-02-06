"""Bitrix token refresh and retry contracts."""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from apps.backend.main import app
from apps.backend.deps import get_db
from apps.backend.auth import create_access_token
from apps.backend.database import get_test_engine, Base
from apps.backend.models.portal import Portal, PortalToken
from apps.backend.services.token_crypto import encrypt_token
from apps.backend.services.portal_tokens import save_tokens, get_access_token, ensure_fresh_access_token, BitrixAuthError
from apps.backend.services.bitrix_auth import rest_call_with_refresh
from apps.backend.clients import bitrix as bitrix_client


def _stub_settings():
    return type("S", (), {
        "token_encryption_key": "x" * 32,
        "secret_key": "y" * 32,
    })()


def _prepare_portal(db, monkeypatch, *, expires_at: datetime | None = None) -> Portal:
    stub_settings = _stub_settings()
    monkeypatch.setattr("apps.backend.services.portal_tokens.get_settings", lambda: stub_settings)
    portal = Portal(
        domain="example.invalid",
        status="active",
        local_client_id="local.id",
        local_client_secret_encrypted=encrypt_token("client_secret", stub_settings.token_encryption_key),
    )
    db.add(portal)
    db.commit()
    db.refresh(portal)
    save_tokens(db, portal.id, "access_old", "refresh_old", expires_in=3600)
    if expires_at is not None:
        row = db.query(PortalToken).filter(PortalToken.portal_id == portal.id).first()
        row.expires_at = expires_at
        db.add(row)
        db.commit()
    return portal


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


@pytest.mark.timeout(10)
def test_rest_call_with_refresh_retries_on_auth_invalid(monkeypatch, test_db_session):
    portal = _prepare_portal(test_db_session, monkeypatch, expires_at=datetime.utcnow() + timedelta(hours=1))
    tokens_used = []

    def fake_rest_call(domain, access_token, method, params, timeout_sec=30):
        tokens_used.append(access_token)
        if len(tokens_used) == 1:
            return None, bitrix_client.BITRIX_ERR_AUTH_INVALID, "The access token provided has expired.", 401
        return {"result": []}, None, "", 200

    def fake_refresh(domain, refresh_token_val, client_id, client_secret):
        return {"access_token": "access_new", "refresh_token": "refresh_new", "expires_in": 3600}, 200, ""

    monkeypatch.setattr(bitrix_client, "rest_call_result_detailed", fake_rest_call)
    monkeypatch.setattr(bitrix_client, "refresh_token", fake_refresh)

    result, err, err_desc, status, refreshed = rest_call_with_refresh(
        test_db_session, portal.id, "imbot.bot.list", {}, "trace-401", timeout_sec=5
    )

    assert refreshed is True
    assert err is None
    assert status == 200
    assert result is not None
    assert len(tokens_used) == 2
    assert tokens_used[0] != tokens_used[1]
    assert get_access_token(test_db_session, portal.id) == "access_new"


@pytest.mark.timeout(10)
def test_get_valid_access_token_refreshes_when_expired(monkeypatch, test_db_session):
    portal = _prepare_portal(test_db_session, monkeypatch, expires_at=datetime.utcnow() - timedelta(seconds=10))

    def fake_refresh(domain, refresh_token_val, client_id, client_secret):
        return {"access_token": "access_new", "refresh_token": "refresh_new", "expires_in": 3600}, 200, ""

    monkeypatch.setattr(bitrix_client, "refresh_token", fake_refresh)

    token = ensure_fresh_access_token(test_db_session, portal.id, skew_seconds=0, trace_id="trace-exp")
    assert token == "access_new"


@pytest.mark.timeout(10)
def test_rest_call_with_refresh_returns_error_when_refresh_fails(monkeypatch, test_db_session):
    portal = _prepare_portal(test_db_session, monkeypatch, expires_at=datetime.utcnow() + timedelta(hours=1))

    def fake_rest_call(domain, access_token, method, params, timeout_sec=30):
        return None, bitrix_client.BITRIX_ERR_AUTH_INVALID, "The access token provided has expired.", 401

    def fake_refresh(domain, refresh_token_val, client_id, client_secret):
        return None, 400, "invalid_grant"

    monkeypatch.setattr(bitrix_client, "rest_call_result_detailed", fake_rest_call)
    monkeypatch.setattr(bitrix_client, "refresh_token", fake_refresh)

    result, err, err_desc, status, refreshed = rest_call_with_refresh(
        test_db_session, portal.id, "imbot.bot.list", {}, "trace-fail", timeout_sec=5
    )

    assert result is None
    assert refreshed is True
    assert err == "bitrix_refresh_failed"
    assert "invalid_grant" in (err_desc or "")
    assert status in (401, 400)


@pytest.mark.timeout(10)
def test_get_valid_access_token_refreshes_once_after_update(monkeypatch, test_db_session):
    portal = _prepare_portal(test_db_session, monkeypatch, expires_at=datetime.utcnow() - timedelta(seconds=1))
    calls = {"count": 0}

    def fake_refresh(domain, refresh_token_val, client_id, client_secret):
        calls["count"] += 1
        return {"access_token": f"access_new_{calls['count']}", "refresh_token": "refresh_new", "expires_in": 3600}, 200, ""

    monkeypatch.setattr(bitrix_client, "refresh_token", fake_refresh)

    first = ensure_fresh_access_token(test_db_session, portal.id, skew_seconds=0, trace_id="trace-a")
    second = ensure_fresh_access_token(test_db_session, portal.id, skew_seconds=0, trace_id="trace-b")

    assert calls["count"] == 1
    assert first == second


@pytest.mark.timeout(10)
def test_admin_refresh_bitrix_endpoint_returns_safe_payload(test_db_session, monkeypatch):
    portal = _prepare_portal(test_db_session, monkeypatch)

    def fake_refresh(db, portal_id, trace_id=None):
        return {"access_token": "secret", "refresh_token": "secret", "expires_in": 1234}

    def _get_db():
        try:
            yield test_db_session
        finally:
            pass

    monkeypatch.setattr("apps.backend.routers.admin_portals.refresh_portal_tokens", fake_refresh)
    app.dependency_overrides[get_db] = _get_db
    try:
        admin_token = create_access_token({"sub": "admin"})
        r = TestClient(app).post(
            f"/v1/admin/portals/{portal.id}/auth/refresh-bitrix",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert "access_token" not in data
    assert "refresh_token" not in data
    assert data.get("expires_in") == 1234


@pytest.mark.timeout(10)
def test_ensure_fresh_access_token_missing_client_credentials(monkeypatch, test_db_session):
    portal = _prepare_portal(test_db_session, monkeypatch, expires_at=datetime.utcnow() - timedelta(seconds=5))
    # Remove client credentials
    portal.local_client_id = None
    portal.local_client_secret_encrypted = None
    test_db_session.add(portal)
    test_db_session.commit()

    with pytest.raises(BitrixAuthError) as exc:
        ensure_fresh_access_token(test_db_session, portal.id, force=True, trace_id="trace-missing")
    assert "missing_client_credentials" in str(exc.value)
