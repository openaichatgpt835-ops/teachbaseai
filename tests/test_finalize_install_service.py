"""Finalize install service: allowlist, ensure_bot, provision; events."""
import json
import pytest
from sqlalchemy.orm import sessionmaker

from apps.backend.database import get_test_engine, Base

_engine = get_test_engine()
if _engine.url.get_backend_name() == "sqlite":
    pytest.skip("SQLite doesn't support JSONB in models; run finalize_install tests on Postgres.", allow_module_level=True)
from apps.backend.models.portal import Portal, PortalUsersAccess
from apps.backend.models.event import Event
from apps.backend.services.finalize_install import finalize_install
import apps.backend.services.finalize_install as fi
import apps.backend.services.bot_provisioning as bp


def test_finalize_install_provisions_and_writes_events(monkeypatch):
    """prepare_chats использует imbot.chat.add затем imbot.message.add с DIALOG_ID=chat{CHAT_ID}."""
    engine = get_test_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    portal = Portal(domain="example.invalid", status="active")
    portal.metadata_json = json.dumps({"bot_id": 123})
    db.add(portal)
    db.commit()
    db.refresh(portal)

    calls = {"chat_add": [], "message_add": []}

    def fake_bot_list(domain, access_token):
        return ([{"id": 123, "code": "teachbase_assistant"}], None)

    def fake_chat_add(domain, access_token, bot_id, user_ids, title=None, message=None):
        calls["chat_add"].append((bot_id, list(user_ids)))
        return 456, None, ""  # CHAT_ID=456

    def fake_message_add(domain, access_token, bot_id, dialog_id, message):
        calls["message_add"].append((bot_id, dialog_id))
        assert dialog_id.startswith("chat"), "DIALOG_ID должен быть chat{CHAT_ID}, не user{id}"
        return True, None, ""

    stub_settings = type("S", (), {"public_base_url": "https://example.com", "token_encryption_key": "x" * 32, "secret_key": "y" * 32})()
    monkeypatch.setattr(bp, "get_settings", lambda: stub_settings)
    monkeypatch.setattr(fi.bitrix_client, "imbot_bot_list", fake_bot_list)
    monkeypatch.setattr(fi.bitrix_client, "imbot_chat_add", fake_chat_add)
    monkeypatch.setattr(fi.bitrix_client, "imbot_message_add", fake_message_add)

    result = finalize_install(
        db,
        portal_id=portal.id,
        selected_user_ids=[1, 2],
        auth_context={"domain": "example.invalid", "access_token": "stub"},
        trace_id="trace-test",
    )

    assert result["status"] == "ok"
    rows = db.query(PortalUsersAccess).filter(PortalUsersAccess.portal_id == portal.id).all()
    assert len(rows) == 2
    assert len(calls["chat_add"]) == 2
    assert len(calls["message_add"]) == 2
    assert calls["message_add"][0][1] == "chat456"
    assert calls["message_add"][1][1] == "chat456"
    events = db.query(Event).filter(Event.portal_id == portal.id, Event.event_type == "install_step").all()
    assert len(events) >= 2


def test_finalize_install_empty_allowlist_skips_provision(monkeypatch):
    """Если allowlist пустой — prepare_chats не вызывается, provision status=skipped."""
    engine = get_test_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    portal = Portal(domain="example.invalid", status="active")
    portal.metadata_json = json.dumps({"bot_id": 123})
    db.add(portal)
    db.commit()
    db.refresh(portal)

    def fake_bot_list(domain, access_token):
        return ([{"id": 123, "code": "teachbase_assistant"}], None)

    chat_add_called = []

    def fake_chat_add(*args, **kwargs):
        chat_add_called.append(1)
        return 456, None, ""

    stub_settings = type("S", (), {"public_base_url": "https://example.com", "token_encryption_key": "x" * 32, "secret_key": "y" * 32})()
    monkeypatch.setattr(bp, "get_settings", lambda: stub_settings)
    monkeypatch.setattr(fi.bitrix_client, "imbot_bot_list", fake_bot_list)
    monkeypatch.setattr(fi.bitrix_client, "imbot_chat_add", fake_chat_add)

    result = finalize_install(
        db,
        portal_id=portal.id,
        selected_user_ids=[],  # пустой allowlist
        auth_context={"domain": "example.invalid", "access_token": "stub"},
        trace_id="trace-empty",
    )

    assert result["status"] == "ok"
    assert result["steps"]["provision"]["status"] == "skipped"
    assert result["steps"]["provision"]["total"] == 0
    assert len(chat_add_called) == 0
