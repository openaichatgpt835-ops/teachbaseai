"""Admin OAuth credentials endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from apps.backend.main import app
from apps.backend.deps import get_db
from apps.backend.database import get_test_engine, Base
from apps.backend.models.portal import Portal
from apps.backend.auth import create_access_token

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
def test_admin_auth_status_and_set_credentials(test_db_session, override_get_db):
    portal = Portal(domain="test.bitrix24.ru", status="active")
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)

    app.dependency_overrides[get_db] = override_get_db
    try:
        admin_token = create_access_token({"sub": "admin"})
        r1 = client.get(
            f"/v1/admin/portals/{portal.id}/auth/status",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r1.status_code == 200
        data1 = r1.json()
        assert data1.get("has_client_id") is False
        assert data1.get("has_client_secret") is False

        r2 = client.post(
            f"/v1/admin/portals/{portal.id}/auth/set-bitrix-credentials",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"client_id": "local.app", "client_secret": "secret"},
        )
        assert r2.status_code == 200
        data2 = r2.json()
        assert data2.get("ok") is True
        assert "client_id_masked" in data2
        assert "client_secret_sha256" in data2

        r3 = client.get(
            f"/v1/admin/portals/{portal.id}/auth/status",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r3.status_code == 200
        data3 = r3.json()
        assert data3.get("has_client_id") is True
        assert data3.get("has_client_secret") is True
    finally:
        app.dependency_overrides.pop(get_db, None)
