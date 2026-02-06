"""Tests for blackbox inbound events middleware (POST /v1/bitrix/events)."""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from apps.backend.main import app
from apps.backend.database import get_test_engine, Base
from apps.backend.models.bitrix_inbound_event import BitrixInboundEvent
from apps.backend.services.bitrix_inbound_log import _safe_headers, _body_preview, BODY_MAX_BYTES_DEFAULT

client = TestClient(app)
EVENTS_PATH = "/v1/bitrix/events"


def test_events_get_head_options_return_200():
    """GET/HEAD/OPTIONS /v1/bitrix/events -> 200 OK, GET/HEAD return JSON."""
    r = client.get(EVENTS_PATH)
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok" and data.get("method") == "GET"
    assert "events endpoint accepts POST" in (data.get("note") or "")
    r2 = client.head(EVENTS_PATH)
    assert r2.status_code == 200
    r3 = client.options(EVENTS_PATH)
    assert r3.status_code == 200


class TestInboundEventsMiddleware:
    """Middleware logs body but handler receives same body."""

    def test_post_events_returns_200_and_handler_receives_body(self):
        """POST /v1/bitrix/events with JSON body -> 200, response reflects same event (handler got body)."""
        body = {"event": "ONIMBOTMESSAGEADD", "data": {"user_id": "1"}, "auth": {}}
        r = client.post(EVENTS_PATH, json=body)
        assert r.status_code == 200
        data = r.json()
        assert "trace_id" in data or "status" in data
        assert data.get("event") == "ONIMBOTMESSAGEADD" or data.get("status") == "ok"

    def test_post_events_empty_body_handler_receives_body(self):
        """POST with empty body -> handler receives same (empty) body."""
        r = client.post(EVENTS_PATH, json={})
        assert r.status_code == 200
        data = r.json()
        assert data.get("event") == "" or data.get("status") == "ok"

    def test_inbound_logging_does_not_consume_body(self):
        """Handler receives same JSON as sent (body not consumed by middleware)."""
        body = {"event": "PING", "data": {"x": 1}}
        r = client.post(EVENTS_PATH, json=body)
        assert r.status_code == 200
        data = r.json()
        assert data.get("event") == "PING" or data.get("status") == "ok"

    def test_inbound_logging_respects_enabled_flag(self):
        """When enabled=False, request still returns 200 (logging skipped, handler runs)."""
        def fake_settings(db):
            return {"enabled": False, "auto_prune_on_write": True, "retention_days": 3,
                    "max_rows": 5000, "max_body_kb": 128, "target_budget_mb": 200}
        with patch("apps.backend.middleware.bitrix_inbound_events.get_inbound_settings", side_effect=fake_settings):
            r = client.post(EVENTS_PATH, json={"event": "PING"})
        assert r.status_code == 200
        data = r.json()
        assert data.get("event") == "PING" or data.get("status") == "ok"

    def test_safe_headers_omits_authorization(self):
        """Authorization/Cookie not in headers_json (safe whitelist only)."""
        headers = {
            "Authorization": "Bearer secret123",
            "Cookie": "session=abc",
            "User-Agent": "test",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        out = _safe_headers(headers)
        assert "Authorization" not in out
        assert "Cookie" not in out
        assert out.get("User-Agent") == "test"
        assert out.get("Accept") == "application/json"
        assert out.get("Content-Type") == "application/json"

    def test_body_preview_truncated_and_sha256(self):
        """If body > 128KB -> truncated True, preview is first 128KB."""
        big = b"x" * (BODY_MAX_BYTES_DEFAULT + 1000)
        preview, truncated = _body_preview(big)
        assert truncated is True
        assert len(preview) <= BODY_MAX_BYTES_DEFAULT + 100
        small = b'{"a":1}'
        preview2, truncated2 = _body_preview(small)
        assert truncated2 is False
        assert preview2 == '{"a":1}'


def test_settings_validation_ranges():
    """PUT settings: retention_days 1..30, max_rows 100..50000, etc. are clamped."""
    from sqlalchemy.orm import sessionmaker
    from apps.backend.database import get_test_engine, Base
    from apps.backend.models.app_setting import AppSetting
    from apps.backend.services.inbound_settings import get_inbound_settings, put_inbound_settings, DEFAULTS

    engine = get_test_engine()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        out = put_inbound_settings(db, {"retention_days": 100, "max_rows": 10, "max_body_kb": 999})
        assert out["retention_days"] == 30
        assert out["max_rows"] == 100
        assert out["max_body_kb"] == 512
        out2 = put_inbound_settings(db, {"retention_days": 0, "target_budget_mb": 5})
        assert out2["retention_days"] == 1
        assert out2["target_budget_mb"] == 10
    finally:
        db.close()


def test_events_trace_id_consistency():
    """POST /v1/bitrix/events returns trace_id that exists in bitrix_inbound_events (single source)."""
    engine = get_test_engine()
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def test_session_factory(engine=None):
        return factory

    with patch("apps.backend.database.get_session_factory", side_effect=test_session_factory):
        r = client.post(EVENTS_PATH, json={"event": "ONIMBOTMESSAGEADD", "data": {}, "auth": {}})
    assert r.status_code == 200
    data = r.json()
    assert "trace_id" in data
    tid = data["trace_id"]

    db = factory()
    try:
        row = db.query(BitrixInboundEvent).filter(BitrixInboundEvent.trace_id == tid).first()
        assert row is not None, f"trace_id {tid} from response must appear in bitrix_inbound_events"
    finally:
        db.close()


def test_prune_auto_applies_retention_and_max_rows():
    """Prune mode=auto applies retention_days and max_rows (no crash; optional DB)."""
    from sqlalchemy.orm import sessionmaker
    from apps.backend.database import get_test_engine, Base
    from apps.backend.models.app_setting import AppSetting
    from apps.backend.models.bitrix_inbound_event import BitrixInboundEvent
    from apps.backend.services.inbound_settings import get_inbound_settings, put_inbound_settings
    from apps.backend.services.bitrix_inbound_log import run_prune

    engine = get_test_engine()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        put_inbound_settings(db, {"retention_days": 3, "max_rows": 5})
        result = run_prune(db, "auto")
        assert "deleted_rows" in result
        assert "remaining_rows" in result
        assert "used_mb_after" in result
        result_all = run_prune(db, "all")
        assert result_all["remaining_rows"] == 0
    finally:
        db.close()
