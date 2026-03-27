from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from apps.backend.database import Base, get_test_engine
from apps.backend.deps import get_db
from apps.backend.main import app
from apps.backend.models.account import Account, AccountIntegration
from apps.backend.models.account_kb_setting import AccountKBSetting
from apps.backend.models.bitrix_inbound_event import BitrixInboundEvent
from apps.backend.models.dialog import Dialog, Message
from apps.backend.models.kb import KBCollection, KBFile, KBSmartFolder, KBSource
from apps.backend.models.portal import Portal
from apps.backend.models.portal_kb_setting import PortalKBSetting
from apps.backend.models.topic_summary import PortalTopicSummary, AccountTopicSummary
from apps.backend.routers import bitrix as bitrix_router
from apps.backend.routers import bitrix_dialogs as bitrix_dialogs_router

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


def _override_get_db(db):
    def _get_db():
        try:
            yield db
        finally:
            pass

    return _get_db


def _seed_account_with_two_portals(db):
    account = Account(name="Account Scope", status="active", account_no=100500)
    db.add(account)
    db.flush()

    portal_a = Portal(domain="b24-a.bitrix24.ru", status="active", admin_user_id=1, account_id=account.id)
    portal_b = Portal(domain="b24-b.bitrix24.ru", status="active", admin_user_id=1, account_id=account.id)
    db.add_all([portal_a, portal_b])
    db.flush()

    db.add_all(
        [
            AccountIntegration(
                account_id=account.id,
                provider="bitrix",
                status="active",
                external_key=portal_a.domain,
                portal_id=portal_a.id,
                credentials_json={"is_primary": True},
            ),
            AccountIntegration(
                account_id=account.id,
                provider="bitrix",
                status="active",
                external_key=portal_b.domain,
                portal_id=portal_b.id,
                credentials_json={"is_primary": False},
            ),
        ]
    )
    db.commit()
    return account, portal_a, portal_b


@pytest.mark.timeout(10)
def test_bitrix_iframe_reads_account_scoped_files_sources_and_settings(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)

    source = KBSource(
        portal_id=portal_a.id,
        source_type="web",
        audience="staff",
        url="https://example.com/doc",
        title="Doc source",
        status="ready",
    )
    test_db_session.add(source)
    test_db_session.flush()
    test_db_session.add(
        KBFile(
            portal_id=portal_a.id,
            source_id=source.id,
            filename="handbook.pdf",
            audience="staff",
            mime_type="application/pdf",
            size_bytes=1234,
            storage_path="/tmp/handbook.pdf",
            status="ready",
            uploaded_by_type="web",
            uploaded_by_id="1",
            uploaded_by_name="Admin",
        )
    )
    test_db_session.add(
        PortalKBSetting(
            portal_id=portal_a.id,
            embedding_model="EmbeddingsGigaR",
            chat_model="GigaChat-2-Max",
            prompt_preset="auto",
            show_sources=True,
        )
    )
    test_db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    original_require_admin = bitrix_router._require_portal_admin
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    try:
        files_resp = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/files",
            headers={"Authorization": "Bearer tok"},
        )
        sources_resp = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/sources",
            headers={"Authorization": "Bearer tok"},
        )
        settings_resp = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/settings",
            headers={"Authorization": "Bearer tok"},
        )
    finally:
        bitrix_router._require_portal_admin = original_require_admin
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert files_resp.status_code == 200
    assert files_resp.json()["items"][0]["filename"] == "handbook.pdf"

    assert sources_resp.status_code == 200
    assert sources_resp.json()["items"][0]["url"] == "https://example.com/doc"

    assert settings_resp.status_code == 200
    assert settings_resp.json()["chat_model"] == "GigaChat-2-Max"
    assert settings_resp.json()["settings_portal_id"] == portal_a.id
    assert settings_resp.json()["settings_account_id"] == account.id


@pytest.mark.timeout(10)
def test_bitrix_kb_settings_save_into_account_scope_and_read_from_second_portal(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    original_require_admin = bitrix_router._require_portal_admin
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    try:
        save_resp = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/kb/settings",
            headers={"Authorization": "Bearer tok"},
            json={
                "embedding_model": "EmbeddingsGigaR",
                "chat_model": "GigaChat-2-Max",
                "prompt_preset": "faq",
                "show_sources": False,
            },
        )
    finally:
        bitrix_router._require_portal_admin = original_require_admin
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert save_resp.status_code == 200
    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_a.id
    original_require_admin = bitrix_router._require_portal_admin
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    try:
        read_resp = client.get(
            f"/v1/bitrix/portals/{portal_a.id}/kb/settings",
            headers={"Authorization": "Bearer tok"},
        )
    finally:
        bitrix_router._require_portal_admin = original_require_admin
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert read_resp.status_code == 200
    assert read_resp.json()["chat_model"] == "GigaChat-2-Max"
    assert read_resp.json()["settings_account_id"] == account.id

    row = test_db_session.get(AccountKBSetting, account.id)
    assert row is not None
    assert row.chat_model == "GigaChat-2-Max"
    assert row.prompt_preset == "faq"


@pytest.mark.timeout(10)
def test_bitrix_iframe_reads_account_scoped_dialogs_and_user_stats(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)
    dialog = Dialog(portal_id=portal_a.id, provider_dialog_id="dlg-1")
    test_db_session.add(dialog)
    test_db_session.flush()
    test_db_session.add(
        Message(
            dialog_id=dialog.id,
            direction="rx",
            body="Где находится регламент по отпуску?",
            created_at=datetime.utcnow(),
        )
    )
    test_db_session.add(
        BitrixInboundEvent(
            portal_id=portal_a.id,
            domain=portal_a.domain,
            event_name="ONIMBOTMESSAGEADD",
            user_id="42",
            method="POST",
            path="/v1/bitrix/events",
            body_truncated=False,
            body_sha256="deadbeef",
            parsed_redacted_json={},
            created_at=datetime.utcnow() - timedelta(hours=1),
        )
    )
    test_db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_dialogs_router.require_portal_access] = lambda: portal_b.id
    try:
        recent_resp = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/dialogs/recent?limit=10",
            headers={"Authorization": "Bearer tok"},
        )
        stats_resp = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/users/stats?hours=24",
            headers={"Authorization": "Bearer tok"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_dialogs_router.require_portal_access, None)

    assert recent_resp.status_code == 200
    assert recent_resp.json()["items"][0]["body"].startswith("Где находится регламент")

    assert stats_resp.status_code == 200
    assert stats_resp.json()["stats"] == {"42": 1}


@pytest.mark.timeout(10)
def test_bitrix_search_reads_account_scoped_kb_from_second_portal(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)
    source = KBSource(
        portal_id=portal_a.id,
        source_type="web",
        audience="staff",
        url="https://example.com/policy",
        title="Policy",
        status="ready",
    )
    test_db_session.add(source)
    test_db_session.flush()
    file = KBFile(
        portal_id=portal_a.id,
        source_id=source.id,
        filename="policy.txt",
        audience="staff",
        mime_type="text/plain",
        size_bytes=10,
        storage_path="/tmp/policy.txt",
        status="ready",
    )
    test_db_session.add(file)
    test_db_session.flush()
    from apps.backend.models.kb import KBChunk

    test_db_session.add(
        KBChunk(
            portal_id=portal_a.id,
            file_id=file.id,
            source_id=source.id,
            audience="staff",
            chunk_index=0,
            text="Регламент по отпуску находится в handbook и policy.",
        )
    )
    test_db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    original_require_admin = bitrix_router._require_portal_admin
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    try:
        resp = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/search?q=%D0%BE%D1%82%D0%BF%D1%83%D1%81%D0%BA&limit=20",
            headers={"Authorization": "Bearer tok"},
        )
    finally:
        bitrix_router._require_portal_admin = original_require_admin
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert resp.status_code == 200
    assert resp.json()["file_ids"] == [file.id]
    assert resp.json()["matches"][0]["filename"] == "policy.txt"


@pytest.mark.timeout(10)
def test_bitrix_ask_uses_account_scoped_file_filter_for_second_portal(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)
    source = KBSource(
        portal_id=portal_a.id,
        source_type="web",
        audience="staff",
        url="https://example.com/policy",
        title="Policy",
        status="ready",
    )
    test_db_session.add(source)
    test_db_session.flush()
    file = KBFile(
        portal_id=portal_a.id,
        source_id=source.id,
        filename="policy.txt",
        audience="staff",
        mime_type="text/plain",
        size_bytes=10,
        storage_path="/tmp/policy.txt",
        status="ready",
    )
    test_db_session.add(file)
    test_db_session.commit()

    captured: dict[str, object] = {}
    original_answer_from_kb = bitrix_router.answer_from_kb

    def _fake_answer_from_kb(db, portal_id, query, **kwargs):
        captured["portal_id"] = portal_id
        captured["file_ids_filter"] = kwargs.get("file_ids_filter")
        return "ok", None, {}

    bitrix_router.answer_from_kb = _fake_answer_from_kb
    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    try:
        resp = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/kb/ask",
            headers={"Authorization": "Bearer tok"},
            json={"query": "Где регламент по отпуску?"},
        )
    finally:
        bitrix_router.answer_from_kb = original_answer_from_kb
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert resp.status_code == 200
    assert resp.json()["answer"] == "ok"
    assert captured["portal_id"] == portal_b.id
    assert captured["file_ids_filter"] == [file.id]


@pytest.mark.timeout(10)
def test_bitrix_ask_uses_current_portal_after_account_runtime_cleanup(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)
    source = KBSource(
        portal_id=portal_a.id,
        source_type="web",
        audience="staff",
        url="https://example.com/policy",
        title="Policy",
        status="ready",
    )
    test_db_session.add(source)
    test_db_session.flush()
    file = KBFile(
        portal_id=portal_a.id,
        source_id=source.id,
        filename="policy.txt",
        audience="staff",
        mime_type="text/plain",
        size_bytes=10,
        storage_path="/tmp/policy.txt",
        status="ready",
    )
    test_db_session.add(file)
    test_db_session.commit()

    calls: list[int] = []
    original_answer_from_kb = bitrix_router.answer_from_kb

    def _fake_answer_from_kb(db, portal_id, query, **kwargs):
        calls.append(int(portal_id))
        return "ok", None, {}

    bitrix_router.answer_from_kb = _fake_answer_from_kb
    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    try:
        resp = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/kb/ask",
            headers={"Authorization": "Bearer tok"},
            json={"query": "test"},
        )
    finally:
        bitrix_router.answer_from_kb = original_answer_from_kb
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert resp.status_code == 200
    assert resp.json()["answer"] == "ok"
    assert calls == [portal_b.id]


@pytest.mark.timeout(10)
def test_bitrix_dialogs_summary_uses_current_portal_runtime_settings(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)
    dialog = Dialog(portal_id=portal_a.id, provider_dialog_id="dlg-2")
    test_db_session.add(dialog)
    test_db_session.flush()
    for idx in range(10):
        test_db_session.add(
            Message(
                dialog_id=dialog.id,
                direction="rx",
                body=f"message-{idx}",
                created_at=datetime.utcnow(),
            )
        )
    test_db_session.commit()

    captured: dict[str, int] = {}
    original_get_settings = bitrix_dialogs_router.get_effective_gigachat_settings
    original_get_token = bitrix_dialogs_router.get_valid_gigachat_access_token
    original_chat_complete = bitrix_dialogs_router.chat_complete

    def _fake_get_settings(db, portal_id):
        captured["portal_id"] = int(portal_id)
        return {"api_base": "https://gigachat.local", "chat_model": "GigaChat-2-Pro"}

    def _fake_get_token(db):
        return "tok", None

    def _fake_chat_complete(api_base, token, model, messages, **kwargs):
        return '[{"topic":"A","score":90},{"topic":"B","score":70},{"topic":"C","score":50}]', None, {}

    bitrix_dialogs_router.get_effective_gigachat_settings = _fake_get_settings
    bitrix_dialogs_router.get_valid_gigachat_access_token = _fake_get_token
    bitrix_dialogs_router.chat_complete = _fake_chat_complete
    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_dialogs_router.require_portal_access] = lambda: portal_b.id
    try:
        resp = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/dialogs/summary?limit=20",
            headers={"Authorization": "Bearer tok"},
        )
    finally:
        bitrix_dialogs_router.chat_complete = original_chat_complete
        bitrix_dialogs_router.get_valid_gigachat_access_token = original_get_token
        bitrix_dialogs_router.get_effective_gigachat_settings = original_get_settings
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_dialogs_router.require_portal_access, None)

    assert resp.status_code == 200
    assert captured["portal_id"] == portal_b.id
    summary = (
        test_db_session.query(AccountTopicSummary)
        .filter(AccountTopicSummary.account_id == account.id)
        .order_by(AccountTopicSummary.id.desc())
        .first()
    )
    assert summary is not None


@pytest.mark.timeout(10)
def test_bitrix_transcript_status_uses_current_portal_runtime_settings(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)
    media = KBFile(
        portal_id=portal_a.id,
        filename="call.mp3",
        audience="staff",
        mime_type="audio/mpeg",
        size_bytes=10,
        storage_path=str(Path("C:/tmp/call.mp3")),
        status="ready",
        transcript_status="ready",
    )
    test_db_session.add(media)
    test_db_session.commit()
    test_db_session.refresh(media)

    captured: dict[str, int] = {}
    original_is_transcription_enabled = bitrix_router.is_media_transcription_enabled

    def _fake_is_transcription_enabled(db, portal_id):
        captured["portal_id"] = int(portal_id)
        return True

    bitrix_router.is_media_transcription_enabled = _fake_is_transcription_enabled
    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    try:
        resp = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/files/{media.id}/transcript/status",
            headers={"Authorization": "Bearer tok"},
        )
    finally:
        bitrix_router.is_media_transcription_enabled = original_is_transcription_enabled
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert resp.status_code == 200
    assert captured["portal_id"] == portal_b.id


@pytest.mark.timeout(10)
def test_bitrix_iframe_writes_new_entities_to_primary_account_portal(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)
    temp_root = Path("tests/.tmp_iframe_account_scope_uploads") / uuid.uuid4().hex
    temp_root.mkdir(parents=True, exist_ok=True)

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    original_require_admin = bitrix_router._require_portal_admin
    original_ensure_portal_dir = bitrix_router.ensure_portal_dir
    original_resolve_uploader = bitrix_router._resolve_uploader
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    bitrix_router.ensure_portal_dir = lambda pid: str(temp_root / f"portal-{pid}")
    bitrix_router._resolve_uploader = lambda db, portal_id, request: ("web", "1", "admin@example.com")
    try:
        upload_resp = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/kb/files/upload",
            headers={"Authorization": "Bearer tok"},
            files={"file": ("new.txt", b"account wide file", "text/plain")},
        )
        source_resp = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/kb/sources/url",
            headers={"Authorization": "Bearer tok"},
            json={"url": "https://example.com/new", "title": "New source"},
        )
        collection_resp = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/kb/collections",
            headers={"Authorization": "Bearer tok"},
            json={"name": "Shared collection", "color": "blue"},
        )
        folder_resp = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/kb/smart-folders",
            headers={"Authorization": "Bearer tok"},
            json={"name": "Shared folder", "rules_json": {"topic": "kb"}},
        )
    finally:
        bitrix_router.ensure_portal_dir = original_ensure_portal_dir
        bitrix_router._require_portal_admin = original_require_admin
        bitrix_router._resolve_uploader = original_resolve_uploader
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert upload_resp.status_code == 200
    uploaded = test_db_session.get(KBFile, int(upload_resp.json()["id"]))
    assert uploaded is not None
    assert uploaded.portal_id == portal_a.id
    assert Path(uploaded.storage_path).name.endswith("new.txt")

    assert source_resp.status_code == 200
    source = test_db_session.get(KBSource, int(source_resp.json()["source_id"]))
    assert source is not None
    assert source.portal_id == portal_a.id

    assert collection_resp.status_code == 200
    collection = test_db_session.get(KBCollection, int(collection_resp.json()["id"]))
    assert collection is not None
    assert collection.portal_id == portal_a.id

    assert folder_resp.status_code == 200
    folder = test_db_session.get(KBSmartFolder, int(folder_resp.json()["id"]))
    assert folder is not None
    assert folder.portal_id == portal_a.id


@pytest.mark.timeout(10)
def test_bitrix_upload_uses_current_portal_runtime_settings_for_media(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)
    temp_root = Path("tests/.tmp_iframe_account_scope_uploads") / uuid.uuid4().hex
    temp_root.mkdir(parents=True, exist_ok=True)

    captured: dict[str, int] = {}
    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    original_require_admin = bitrix_router._require_portal_admin
    original_ensure_portal_dir = bitrix_router.ensure_portal_dir
    original_resolve_uploader = bitrix_router._resolve_uploader
    original_is_transcription_enabled = bitrix_router.is_media_transcription_enabled
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    bitrix_router.ensure_portal_dir = lambda pid: str(temp_root / f"portal-{pid}")
    bitrix_router._resolve_uploader = lambda db, portal_id, request: ("web", "1", "admin@example.com")

    def _fake_is_transcription_enabled(db, portal_id):
        captured["portal_id"] = int(portal_id)
        return False

    bitrix_router.is_media_transcription_enabled = _fake_is_transcription_enabled
    try:
        upload_resp = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/kb/files/upload",
            headers={"Authorization": "Bearer tok"},
            files={"file": ("call.mp3", b"fake-mp3", "audio/mpeg")},
        )
    finally:
        bitrix_router.is_media_transcription_enabled = original_is_transcription_enabled
        bitrix_router.ensure_portal_dir = original_ensure_portal_dir
        bitrix_router._require_portal_admin = original_require_admin
        bitrix_router._resolve_uploader = original_resolve_uploader
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert upload_resp.status_code == 200
    assert captured["portal_id"] == portal_b.id


@pytest.mark.timeout(10)
def test_bitrix_iframe_can_mutate_primary_portal_resources_from_second_portal(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)
    temp_root = Path("tests/.tmp_iframe_account_scope_uploads") / uuid.uuid4().hex
    temp_root.mkdir(parents=True, exist_ok=True)
    shared_path = temp_root / "shared.txt"
    shared_path.write_text("hello", encoding="utf-8")
    file = KBFile(
        portal_id=portal_a.id,
        filename="shared.txt",
        audience="staff",
        mime_type="text/plain",
        size_bytes=5,
        storage_path=str(shared_path),
        status="ready",
    )
    test_db_session.add(file)
    test_db_session.flush()
    file_id = int(file.id)
    collection = KBCollection(portal_id=portal_a.id, name="Shared", color="red")
    folder = KBSmartFolder(portal_id=portal_a.id, name="Folder", rules_json={"x": 1})
    test_db_session.add_all([collection, folder])
    test_db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    original_require_admin = bitrix_router._require_portal_admin
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    try:
        add_resp = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/kb/collections/{collection.id}/files",
            headers={"Authorization": "Bearer tok"},
            json={"file_id": file_id},
        )
        reindex_resp = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/kb/files/{file_id}/reindex",
            headers={"Authorization": "Bearer tok"},
        )
        folder_delete_resp = client.delete(
            f"/v1/bitrix/portals/{portal_b.id}/kb/smart-folders/{folder.id}",
            headers={"Authorization": "Bearer tok"},
        )
        collection_remove_resp = client.delete(
            f"/v1/bitrix/portals/{portal_b.id}/kb/collections/{collection.id}/files/{file_id}",
            headers={"Authorization": "Bearer tok"},
        )
        delete_file_resp = client.delete(
            f"/v1/bitrix/portals/{portal_b.id}/kb/files/{file_id}",
            headers={"Authorization": "Bearer tok"},
        )
    finally:
        bitrix_router._require_portal_admin = original_require_admin
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert add_resp.status_code == 200
    assert reindex_resp.status_code == 200
    assert folder_delete_resp.status_code == 200
    assert collection_remove_resp.status_code == 200
    assert delete_file_resp.status_code == 200
    assert test_db_session.get(KBSmartFolder, folder.id) is None
    assert test_db_session.get(KBFile, file_id) is None
