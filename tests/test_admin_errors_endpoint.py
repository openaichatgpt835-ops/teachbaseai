"""Admin errors feed endpoint tests."""

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
def test_admin_errors_unified_feed(test_db_session, override_get_db):
    portal = Portal(domain="foo.bitrix24.ru", status="active")
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)

    test_db_session.add(
        BitrixHttpLog(
            trace_id="tr-1",
            portal_id=portal.id,
            direction="out",
            kind="bitrix_rest",
            method="POST",
            path="/rest/user.get",
            status_code=403,
            summary_json=json.dumps({"error_code": "missing_scope_user", "error_description_safe": "scope missing"}),
        )
    )
    test_db_session.add(
        BitrixInboundEvent(
            trace_id="tr-2",
            portal_id=portal.id,
            domain=portal.domain,
            event_name="ONIMBOTMESSAGEADD",
            method="POST",
            path="/v1/bitrix/events",
            body_truncated=False,
            body_sha256="x" * 64,
            status_hint="denied",
            hints_json={"reason": "acl_denied"},
        )
    )
    test_db_session.add(
        Outbox(
            portal_id=portal.id,
            status="error",
            payload_json=json.dumps({"trace_id": "tr-3", "kind": "telegram_send"}),
            error_message="telegram http 403 forbidden",
        )
    )
    test_db_session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        admin_token = create_access_token({"sub": "admin"})
        r = client.get(
            "/v1/admin/errors?limit=50",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    data = r.json()
    channels = {x.get("channel") for x in data.get("items", [])}
    assert "bitrix_http" in channels
    assert "inbound" in channels
    assert "outbox" in channels


@pytest.mark.timeout(10)
def test_admin_errors_filter_by_partial_domain(test_db_session, override_get_db):
    portal1 = Portal(domain="s57ni9.bitrix24.ru", status="active")
    portal2 = Portal(domain="other.bitrix24.ru", status="active")
    test_db_session.add(portal1)
    test_db_session.add(portal2)
    test_db_session.commit()
    test_db_session.refresh(portal1)
    test_db_session.refresh(portal2)

    test_db_session.add(
        BitrixHttpLog(
            trace_id="tr-a",
            portal_id=portal1.id,
            direction="out",
            kind="bitrix_rest",
            method="POST",
            path="/rest/user.get",
            status_code=403,
            summary_json=json.dumps({"error_code": "missing_scope_user"}),
        )
    )
    test_db_session.add(
        BitrixHttpLog(
            trace_id="tr-b",
            portal_id=portal2.id,
            direction="out",
            kind="bitrix_rest",
            method="POST",
            path="/rest/user.get",
            status_code=403,
            summary_json=json.dumps({"error_code": "missing_scope_user"}),
        )
    )
    test_db_session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        admin_token = create_access_token({"sub": "admin"})
        r = client.get(
            "/v1/admin/errors?portal=s57ni9",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    items = r.json().get("items", [])
    assert len(items) >= 1
    assert all("s57ni9" in (it.get("portal_domain") or "") for it in items)


@pytest.mark.timeout(10)
def test_admin_errors_export_csv_and_json(test_db_session, override_get_db):
    portal = Portal(domain="export.bitrix24.ru", status="active")
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)
    test_db_session.add(
        BitrixHttpLog(
            trace_id="tr-export",
            portal_id=portal.id,
            direction="out",
            kind="bitrix_rest",
            method="POST",
            path="/rest/user.get",
            status_code=403,
            summary_json=json.dumps({"error_code": "missing_scope_user"}),
        )
    )
    test_db_session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        admin_token = create_access_token({"sub": "admin"})
        r_json = client.get(
            "/v1/admin/errors/export.json?portal=export",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        r_csv = client.get(
            "/v1/admin/errors/export.csv?portal=export",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r_json.status_code == 200
    assert r_json.json().get("total", 0) >= 1
    assert r_csv.status_code == 200
    assert "text/csv" in (r_csv.headers.get("content-type") or "")
    assert "api_errors.csv" in (r_csv.headers.get("content-disposition") or "")


@pytest.mark.timeout(10)
def test_admin_errors_summary(test_db_session, override_get_db):
    portal = Portal(domain="sum.bitrix24.ru", status="active")
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)
    test_db_session.add(
        BitrixHttpLog(
            trace_id="tr-s1",
            portal_id=portal.id,
            direction="out",
            kind="bitrix_rest",
            method="POST",
            path="/rest/user.get",
            status_code=200,
            latency_ms=120,
            summary_json=json.dumps({}),
        )
    )
    test_db_session.add(
        BitrixHttpLog(
            trace_id="tr-s2",
            portal_id=portal.id,
            direction="out",
            kind="bitrix_rest",
            method="POST",
            path="/rest/user.get",
            status_code=403,
            latency_ms=250,
            summary_json=json.dumps({"error_code": "missing_scope_user"}),
        )
    )
    test_db_session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        admin_token = create_access_token({"sub": "admin"})
        r = client.get(
            "/v1/admin/errors/summary?period=24h",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    data = r.json()
    assert data.get("bitrix_total_requests") >= 2
    assert data.get("bitrix_error_requests") >= 1
    assert isinstance(data.get("error_rate_percent"), float)
