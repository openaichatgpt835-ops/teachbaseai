"""OAuth refresh flow contract."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from sqlalchemy.orm import sessionmaker

from apps.backend.database import get_test_engine, Base
from apps.backend.models.portal import Portal, PortalToken
from apps.backend.services.token_crypto import encrypt_token
from apps.backend.services.portal_tokens import ensure_fresh_access_token, BitrixAuthError
from apps.backend.clients import bitrix as bitrix_client


def _db():
    engine = get_test_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@pytest.mark.timeout(10)
def test_refresh_flow_updates_tokens(monkeypatch):
    db = _db()
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
    db.add(portal)
    db.commit()
    db.refresh(portal)

    row = PortalToken(portal_id=portal.id, access_token=encrypt_token("old", stub_settings.token_encryption_key), refresh_token=encrypt_token("r1", stub_settings.token_encryption_key), expires_at=datetime.utcnow() - timedelta(minutes=1))
    db.add(row)
    db.commit()

    def fake_refresh(domain, refresh_token_val, client_id, client_secret):
        return {"access_token": "new", "refresh_token": "r2", "expires_in": 3600}, 200, ""

    monkeypatch.setattr(bitrix_client, "refresh_token", fake_refresh)

    token = ensure_fresh_access_token(db, portal.id, trace_id="t1", force=True)
    assert token == "new"


@pytest.mark.timeout(10)
def test_refresh_missing_creds(monkeypatch):
    db = _db()
    stub_settings = type("S", (), {
        "token_encryption_key": "x" * 32,
        "secret_key": "y" * 32,
        "bitrix_client_id": "",
        "bitrix_client_secret": "",
    })()
    monkeypatch.setattr("apps.backend.services.portal_tokens.get_settings", lambda: stub_settings)

    portal = Portal(domain="example.invalid", status="active")
    db.add(portal)
    db.commit()
    db.refresh(portal)

    row = PortalToken(portal_id=portal.id, access_token=encrypt_token("old", stub_settings.token_encryption_key), refresh_token=encrypt_token("r1", stub_settings.token_encryption_key), expires_at=datetime.utcnow() - timedelta(minutes=1))
    db.add(row)
    db.commit()

    with pytest.raises(BitrixAuthError) as exc:
        ensure_fresh_access_token(db, portal.id, trace_id="t2", force=True)
    assert "missing_client_credentials" in str(exc.value)
