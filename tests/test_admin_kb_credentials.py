"""Admin KB credentials endpoint updates auth_key and auto-refresh token."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

from apps.backend.main import app
from apps.backend.deps import get_db
from apps.backend.database import get_test_engine, Base
from apps.backend.auth import create_access_token
from apps.backend.services.kb_settings import (
    get_gigachat_auth_key_plain,
    get_gigachat_access_token_plain,
    set_gigachat_settings,
)


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
def test_admin_kb_credentials_updates_auth_key_and_token(test_db_session, override_get_db, monkeypatch):
    app.dependency_overrides[get_db] = override_get_db
    try:
        admin_token = create_access_token({"sub": "admin"})

        def fake_request_access_token(auth_key: str, scope: str):
            assert auth_key
            assert scope == "GIGACHAT_API_PERS"
            return "token-1", 1700000000, None

        monkeypatch.setattr(
            "apps.backend.routers.admin_kb.request_access_token",
            fake_request_access_token,
        )

        r1 = client.post(
            "/v1/admin/kb/credentials",
            headers={"Authorization": f"Bearer {admin_token}"},
            data={
                "client_id": "client-1",
                "auth_key": "key-1",
                "scope": "GIGACHAT_API_PERS",
            },
        )
        assert r1.status_code == 200
        data1 = r1.json()
        assert data1.get("has_auth_key") is True
        assert data1.get("auth_key_input_len") == len("key-1")
        assert data1.get("has_access_token") is True
        assert data1.get("access_token_expires_at") == 1700000000
        assert get_gigachat_auth_key_plain(test_db_session) == "key-1"
        assert get_gigachat_access_token_plain(test_db_session) == "token-1"

        def fake_request_access_token2(auth_key: str, scope: str):
            assert auth_key == "key-2"
            assert scope == "GIGACHAT_API_PERS"
            return "token-2", 1700000001, None

        monkeypatch.setattr(
            "apps.backend.routers.admin_kb.request_access_token",
            fake_request_access_token2,
        )

        r2 = client.post(
            "/v1/admin/kb/credentials",
            headers={"Authorization": f"Bearer {admin_token}"},
            data={
                "auth_key": "key-2",
                "scope": "GIGACHAT_API_PERS",
            },
        )
        assert r2.status_code == 200
        data2 = r2.json()
        assert data2.get("has_auth_key") is True
        assert data2.get("auth_key_input_len") == len("key-2")
        assert get_gigachat_auth_key_plain(test_db_session) == "key-2"
        assert get_gigachat_access_token_plain(test_db_session) == "token-2"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.timeout(10)
def test_admin_kb_credentials_health_reports_broken_orphan_token(test_db_session, override_get_db):
    app.dependency_overrides[get_db] = override_get_db
    try:
        admin_token = create_access_token({"sub": "admin"})
        set_gigachat_settings(
            test_db_session,
            api_base="https://gigachat.devices.sberbank.ru/api/v1",
            model="",
            embedding_model="EmbeddingsGigaR",
            chat_model="GigaChat-Pro",
            client_id=None,
            auth_key="",
            scope="GIGACHAT_API_PERS",
            client_secret=None,
            access_token="cached-token",
            access_token_expires_at=int((datetime.utcnow() + timedelta(minutes=10)).timestamp()),
        )
        r = client.get(
            "/v1/admin/kb/credentials/health",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "broken"
        assert "missing_auth_key" in data["issues"]
        assert "orphan_access_token" in data["issues"]
        assert data["can_refresh"] is False
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.timeout(10)
def test_admin_kb_credentials_health_reports_warning_on_expired_cached_token(test_db_session, override_get_db, monkeypatch):
    app.dependency_overrides[get_db] = override_get_db
    try:
        admin_token = create_access_token({"sub": "admin"})
        set_gigachat_settings(
            test_db_session,
            api_base="https://gigachat.devices.sberbank.ru/api/v1",
            model="",
            embedding_model="EmbeddingsGigaR",
            chat_model="GigaChat-Pro",
            client_id=None,
            auth_key="key-1",
            scope="GIGACHAT_API_PERS",
            client_secret=None,
            access_token="expired-token",
            access_token_expires_at=int((datetime.utcnow() - timedelta(minutes=5)).timestamp()),
        )

        monkeypatch.setattr(
            "apps.backend.services.gigachat_client.request_access_token_detailed",
            lambda auth_key, scope: ("fresh-token", int((datetime.utcnow() + timedelta(minutes=30)).timestamp()), None, 200),
        )

        r = client.get(
            "/v1/admin/kb/credentials/health",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "warning"
        assert "access_token_expired" in data["issues"]
        assert data["oauth_probe"]["ok"] is True
        assert data["can_refresh"] is True
    finally:
        app.dependency_overrides.pop(get_db, None)
