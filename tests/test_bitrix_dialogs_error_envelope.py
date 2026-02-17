"""Bitrix dialogs error envelope tests."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from apps.backend.main import app
from apps.backend.deps import get_db
from apps.backend.database import Base, get_test_engine
from apps.backend.models.portal import Portal
from apps.backend.models.dialog import Dialog, Message
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
def test_dialogs_summary_gigachat_unavailable_envelope(test_db_session, override_get_db):
    portal = Portal(domain="dlg.bitrix24.ru", status="active", admin_user_id=1)
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)
    token = create_portal_token_with_user(portal.id, user_id=1, expires_minutes=10)
    dialog = Dialog(portal_id=portal.id, provider_dialog_id="chat1")
    test_db_session.add(dialog)
    test_db_session.commit()
    test_db_session.refresh(dialog)
    for i in range(10):
        test_db_session.add(
            Message(
                dialog_id=dialog.id,
                direction="rx",
                body=f"msg {i}",
            )
        )
    test_db_session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("apps.backend.routers.bitrix_dialogs.get_valid_gigachat_access_token", return_value=(None, "token_error")):
            r = client.get(
                f"/v1/bitrix/portals/{portal.id}/dialogs/summary",
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 503
    data = r.json()
    assert data.get("error") == "gigachat_unavailable"
    assert data.get("code") == "gigachat_unavailable"
    assert "trace_id" in data
