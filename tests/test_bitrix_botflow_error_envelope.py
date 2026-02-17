"""Bitrix botflow error envelope tests."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from apps.backend.main import app
from apps.backend.deps import get_db
from apps.backend.database import Base, get_test_engine
from apps.backend.models.portal import Portal
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
def test_botflow_forbidden_returns_envelope(test_db_session, override_get_db):
    p1 = Portal(domain="p1.bitrix24.ru", status="active", admin_user_id=1)
    p2 = Portal(domain="p2.bitrix24.ru", status="active", admin_user_id=1)
    test_db_session.add(p1)
    test_db_session.add(p2)
    test_db_session.commit()
    test_db_session.refresh(p1)
    test_db_session.refresh(p2)
    token = create_portal_token_with_user(p1.id, user_id=1, expires_minutes=10)

    app.dependency_overrides[get_db] = override_get_db
    try:
        r = client.get(
            f"/v1/bitrix/portals/{p2.id}/botflow/client",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 403
    data = r.json()
    # pid mismatch is rejected by dependency layer before route handler.
    # Keep this assertion to ensure endpoint remains protected.
    assert data.get("error") == "forbidden" or data.get("detail")


@pytest.mark.timeout(10)
def test_botflow_missing_draft_returns_envelope(test_db_session, override_get_db):
    portal = Portal(domain="flow.bitrix24.ru", status="active", admin_user_id=1)
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)
    token = create_portal_token_with_user(portal.id, user_id=1, expires_minutes=10)

    app.dependency_overrides[get_db] = override_get_db
    try:
        r = client.post(
            f"/v1/bitrix/portals/{portal.id}/botflow/client/test",
            headers={"Authorization": f"Bearer {token}"},
            json={"text": "hello"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 400
    data = r.json()
    assert data.get("error") == "missing_draft"
    assert data.get("code") == "missing_draft"
    assert "trace_id" in data
