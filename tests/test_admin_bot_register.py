"""POST /v1/admin/portals/{id}/bot/register: expected JSON structure and event logging."""
import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from sqlalchemy.orm import sessionmaker

from apps.backend.main import app
from apps.backend.deps import get_db
from apps.backend.database import get_test_engine, Base
from apps.backend.models.portal import Portal, PortalToken
from apps.backend.models.event import Event
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


@pytest.mark.timeout(15)
def test_admin_bot_register_returns_expected_structure_and_writes_event(test_db_session, override_get_db):
    """POST /v1/admin/portals/{id}/bot/register returns status, trace_id, portal_id, bot, event_urls_sent; writes Event bot_register."""
    portal = Portal(domain="test.bitrix24.ru", status="active")
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)
    portal_id = portal.id

    def fake_ensure_bot(db, pid, trace_id, **kwargs):
        return {
            "ok": True,
            "bot_id": 999,
            "application_token_present": True,
            "error_code": None,
            "error_detail_safe": None,
            "event_urls_sent": ["https://necrogame.ru/api/v1/bitrix/events"],
        }

    app.dependency_overrides[get_db] = override_get_db
    try:
        admin_token = create_access_token({"sub": "admin"})
        with patch("apps.backend.routers.admin_portals.ensure_bot_registered", side_effect=fake_ensure_bot):
            r = client.post(
                f"/v1/admin/portals/{portal_id}/bot/register",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "application/json" in ct
    data = r.json()
    assert "status" in data
    assert data["status"] in ("ok", "error")
    assert "trace_id" in data
    assert data["portal_id"] == portal_id
    assert "bot" in data
    bot = data["bot"]
    assert "status" in bot
    assert "bot_id_present" in bot
    assert "error_code" in bot
    assert "error_description_safe" in bot
    assert "event_urls_sent" in data
    assert isinstance(data["event_urls_sent"], list)

    events = test_db_session.query(Event).filter(
        Event.portal_id == portal_id,
        Event.event_type == "bot_register",
    ).all()
    assert len(events) >= 1
    payload = json.loads(events[-1].payload_json or "{}")
    assert payload.get("trace_id") == data["trace_id"]
    assert payload.get("status") in ("ok", "error")
