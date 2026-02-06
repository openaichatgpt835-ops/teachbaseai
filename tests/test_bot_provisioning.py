"""Bot provisioning: ensure_bot_registered idempotent, bot status in complete; bitrix_http_logs for imbot.register."""
import json
from unittest.mock import patch

import pytest
from sqlalchemy.orm import sessionmaker

from apps.backend.database import get_test_engine, Base

_engine = get_test_engine()
if _engine.url.get_backend_name() == "sqlite":
    pytest.skip("SQLite doesn't support JSONB in models; run bot provisioning tests on Postgres.", allow_module_level=True)
from apps.backend.models.portal import Portal
from apps.backend.models.bitrix_log import BitrixHttpLog
from apps.backend.services.bot_provisioning import ensure_bot_registered
import apps.backend.services.bot_provisioning as bp
from apps.backend.clients import bitrix as bitrix_client
from apps.backend.clients.bitrix import BOT_NAME_DEFAULT, BOT_CODE_DEFAULT


def test_ensure_bot_registered_idempotent():
    """Если bot_id в БД и imbot.bot.list возвращает этого бота — imbot.register не вызывается."""
    engine = get_test_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    portal = Portal(domain="example.invalid", status="active")
    portal.metadata_json = json.dumps({"bot_id": 456, "bot_app_token_enc": "enc_stub"})
    db.add(portal)
    db.commit()
    db.refresh(portal)

    def fake_bot_list(domain, access_token):
        return ([{"id": 456, "code": BOT_CODE_DEFAULT}], None)

    with patch.object(bp.bitrix_client, "imbot_bot_list", side_effect=fake_bot_list), \
         patch.object(bp.bitrix_client, "imbot_register") as m:
        result = ensure_bot_registered(db, portal.id, "trace-id", domain="https://example.invalid", access_token="stub")
        m.assert_not_called()
    assert result["ok"] is True
    assert result["bot_id"] == 456
    assert result["application_token_present"] is True


def test_ensure_bot_found_by_code_without_stored_bot_id(monkeypatch):
    """Если bot_id нет в БД, но imbot.bot.list находит бота по CODE — сохраняем bot_id и не вызываем register."""
    engine = get_test_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    portal = Portal(domain="example.invalid", status="active")
    db.add(portal)
    db.commit()
    db.refresh(portal)

    def fake_bot_list(domain, access_token):
        return ([{"id": 999, "code": BOT_CODE_DEFAULT}], None)

    with patch.object(bp.bitrix_client, "imbot_bot_list", side_effect=fake_bot_list), \
         patch.object(bp.bitrix_client, "imbot_register") as m:
        stub_settings = type("S", (), {"public_base_url": "https://example.com", "token_encryption_key": "x" * 32, "secret_key": "y" * 32})()
        monkeypatch.setattr(bp, "get_settings", lambda: stub_settings)
        result = ensure_bot_registered(db, portal.id, "trace-code", domain="https://example.invalid", access_token="stub")
        m.assert_not_called()
    assert result["ok"] is True
    assert result["bot_id"] == 999
    db.refresh(portal)
    meta = json.loads(portal.metadata_json or "{}")
    assert meta.get("bot_id") == 999


def test_ensure_bot_register_success(monkeypatch):
    """Mock Bitrix -> bot_id и application_token сохраняются в БД. imbot.bot.list пустой -> imbot.register."""
    engine = get_test_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    portal = Portal(domain="example.invalid", status="active")
    db.add(portal)
    db.commit()
    db.refresh(portal)

    def fake_bot_list(domain, access_token):
        return ([], None)

    def fake_register(domain, access_token, events_base_url=None, trace_id=None, portal_id=None):
        return (
            {"bot_id": 789, "app_token": "secret_token"},
            None,
            "",
            ["https://example.com/api/v1/bitrix/events"],
            200,
            0,
            {},
        )

    monkeypatch.setattr(bp.bitrix_client, "imbot_bot_list", fake_bot_list)
    monkeypatch.setattr(bp.bitrix_client, "imbot_register", fake_register)
    stub_settings = type("S", (), {"public_base_url": "https://example.com", "token_encryption_key": "x" * 32, "secret_key": "y" * 32})()
    monkeypatch.setattr(bp, "get_settings", lambda: stub_settings)

    result = ensure_bot_registered(db, portal.id, "trace-id", domain="https://example.invalid", access_token="stub")
    assert result["ok"] is True
    assert result["bot_id"] == 789
    assert result["application_token_present"] is True

    db.refresh(portal)
    meta = json.loads(portal.metadata_json or "{}")
    assert meta.get("bot_id") == 789
    assert "bot_app_token_enc" in meta


def test_ensure_bot_register_error_saves_to_bitrix_http_logs(monkeypatch):
    """When imbot.register returns error, bitrix_http_logs gets row with error_code and error_description_safe (no secrets)."""
    engine = get_test_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    portal = Portal(domain="example.invalid", status="active")
    db.add(portal)
    db.commit()
    db.refresh(portal)

    def fake_bot_list(domain, access_token):
        return ([], None)

    def fake_register(domain, access_token, events_base_url=None, trace_id=None, portal_id=None):
        return (
            {"error": "EVENT_URL_INVALID", "error_description": "URL not accessible"},
            "EVENT_URL_INVALID",
            "Event handler URL is not accessible",
            ["https://necrogame.ru/api/v1/bitrix/events"],
            400,
            50,
            {},
        )

    monkeypatch.setattr(bp.bitrix_client, "imbot_bot_list", fake_bot_list)
    monkeypatch.setattr(bp.bitrix_client, "imbot_register", fake_register)
    stub_settings = type("S", (), {"public_base_url": "https://necrogame.ru", "token_encryption_key": "x" * 32, "secret_key": "y" * 32})()
    monkeypatch.setattr(bp, "get_settings", lambda: stub_settings)

    result = ensure_bot_registered(db, portal.id, "trace-err-1", domain="https://example.invalid", access_token="stub")
    assert result["ok"] is False
    assert result["error_code"] == "EVENT_URL_INVALID"

    rows = db.query(BitrixHttpLog).filter(
        BitrixHttpLog.trace_id == "trace-err-1",
        BitrixHttpLog.kind == "imbot_register",
    ).all()
    assert len(rows) >= 1
    summary = json.loads(rows[-1].summary_json or "{}")
    assert summary.get("error_code") == "EVENT_URL_INVALID"
    assert "error_description_safe" in summary
    assert "event_urls_sent" in summary
    assert "https://necrogame.ru" in str(summary.get("event_urls_sent", []))
    assert "request_shape_json" in summary
    assert "response_shape_json" in summary
    req_shape = summary.get("request_shape_json") or {}
    assert "access_token" not in str(req_shape).lower() and "auth" not in req_shape


@pytest.mark.timeout(15)
def test_imbot_register_payload_form_urlencoded_and_properties_name():
    """imbot.register: flat params (form-urlencoded), PROPERTIES[NAME], EVENT_MESSAGE_ADD = /v1/bitrix/events, sent_keys."""
    captured = {}

    def capture_detailed(domain, access_token, method, params=None, **kwargs):
        if method == "imbot.register" and params:
            captured["params"] = {k: v for k, v in params.items() if k != "auth"}
        return ({"bot_id": 1, "app_token": "***"}, None, "", 200)

    with patch.object(bitrix_client, "rest_call_result_detailed", side_effect=capture_detailed):
        bitrix_client.imbot_register(
            "***.invalid",
            "***",
            events_base_url="https://necrogame.ru",
            trace_id="trace-name-test",
            portal_id=1,
        )
    assert "params" in captured
    p = captured["params"]
    assert "PROPERTIES[NAME]" in p, "Bitrix expects PROPERTIES[NAME] (form-urlencoded)"
    assert p.get("PROPERTIES[NAME]") == BOT_NAME_DEFAULT
    assert p.get("CODE") == BOT_CODE_DEFAULT
    assert p.get("TYPE") == "B"
    ev = p.get("EVENT_MESSAGE_ADD") or ""
    assert "/v1/bitrix/events" in ev
    assert "bitrix24" not in ev.lower()
    assert "auth" not in p or p.get("auth") == "***"
