"""Admin trace timeline endpoint tests."""

import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from apps.backend.main import app
from apps.backend.deps import get_db
from apps.backend.database import Base, get_test_engine
from apps.backend.auth import create_access_token
from apps.backend.models.portal import Portal
from apps.backend.models.bitrix_log import BitrixHttpLog
from apps.backend.models.bitrix_inbound_event import BitrixInboundEvent
from apps.backend.models.outbox import Outbox

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
def test_trace_timeline_combines_sources(test_db_session, override_get_db):
    portal = Portal(domain="timeline.bitrix24.ru", status="active")
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)
    trace_id = "trace-timeline-1"

    test_db_session.add(
        BitrixHttpLog(
            trace_id=trace_id,
            portal_id=portal.id,
            direction="out",
            kind="bitrix_rest",
            method="POST",
            path="/rest/user.get",
            status_code=403,
            summary_json=json.dumps({"error_code": "missing_scope_user"}),
        )
    )
    test_db_session.add(
        BitrixInboundEvent(
            trace_id=trace_id,
            portal_id=portal.id,
            domain=portal.domain,
            event_name="ONIMBOTMESSAGEADD",
            method="POST",
            path="/v1/bitrix/events",
            body_truncated=False,
            body_sha256="x" * 64,
            status_hint="ok",
        )
    )
    test_db_session.add(
        Outbox(
            portal_id=portal.id,
            status="error",
            payload_json=json.dumps({"trace_id": trace_id, "kind": "telegram_send"}),
            error_message="timeout",
        )
    )
    test_db_session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        admin_token = create_access_token({"sub": "admin"})
        r = client.get(
            f"/v1/admin/traces/{trace_id}/timeline",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    data = r.json()
    src = {x.get("source") for x in data.get("items", [])}
    assert "bitrix_http" in src
    assert "inbound" in src
    assert "outbox" in src


@pytest.mark.timeout(10)
def test_trace_detail_exposes_request_and_response_json(test_db_session, override_get_db):
    portal = Portal(domain="trace-detail.bitrix24.ru", status="active")
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)
    trace_id = "trace-detail-json-1"

    summary = {
        "request_json": {"portal_id": 18, "client_secret": "[MASKED]"},
        "response_json": {"error": "forbidden", "code": "forbidden"},
        "headers_min": {"content_type": "application/json"},
    }
    test_db_session.add(
        BitrixHttpLog(
            trace_id=trace_id,
            portal_id=portal.id,
            direction="inbound",
            kind="request",
            method="POST",
            path="/v1/bitrix/portals/18/bitrix/credentials",
            status_code=403,
            summary_json=json.dumps(summary),
        )
    )
    test_db_session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        admin_token = create_access_token({"sub": "admin"})
        r = client.get(
            f"/v1/admin/traces/{trace_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    data = r.json()
    assert data["items"][0]["request_json"]["portal_id"] == 18
    assert data["items"][0]["response_json"]["code"] == "forbidden"
    assert data["items"][0]["headers_min"]["content_type"] == "application/json"
