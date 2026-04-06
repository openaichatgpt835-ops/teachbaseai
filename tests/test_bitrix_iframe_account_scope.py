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
from apps.backend.models.account import (
    Account,
    AccountIntegration,
    AccountMembership,
    AccountUserGroup,
    AccountUserGroupMember,
    AppUser,
    AppUserIdentity,
)
from apps.backend.models.account_kb_setting import AccountKBSetting
from apps.backend.models.bitrix_inbound_event import BitrixInboundEvent
from apps.backend.models.dialog import Dialog, Message
from apps.backend.models.kb import KBChunk, KBCollection, KBCollectionFile, KBFile, KBFileAccess, KBFolder, KBFolderAccess, KBJob, KBSmartFolder, KBSource
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
    assert settings_resp.json()["settings_scope"] == "account"
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
    assert read_resp.json()["settings_scope"] == "account"
    assert read_resp.json()["settings_account_id"] == account.id

    row = test_db_session.get(AccountKBSetting, account.id)
    assert row is not None
    assert row.chat_model == "GigaChat-2-Max"
    assert row.prompt_preset == "faq"


@pytest.mark.timeout(10)
def test_bitrix_iframe_can_read_chunks_from_account_scoped_file(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)
    source = KBSource(account_id=account.id, portal_id=portal_a.id, source_type="file", audience="staff", title="Doc", status="ready")
    test_db_session.add(source)
    test_db_session.flush()
    file_row = KBFile(
        account_id=account.id,
        portal_id=portal_a.id,
        source_id=source.id,
        filename="doc.txt",
        audience="staff",
        mime_type="text/plain",
        size_bytes=10,
        storage_path="/tmp/doc.txt",
        status="ready",
    )
    test_db_session.add(file_row)
    test_db_session.flush()
    test_db_session.add(KBChunk(portal_id=portal_a.id, file_id=file_row.id, source_id=source.id, audience="staff", chunk_index=0, text="alpha beta"))
    test_db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    try:
        resp = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/files/{file_row.id}/chunks",
            headers={"Authorization": "Bearer tok"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["text"] == "alpha beta"

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
    assert uploaded.account_id == account.id
    assert uploaded.portal_id == portal_a.id
    assert Path(uploaded.storage_path).name.endswith("new.txt")

    assert source_resp.status_code == 200
    source = test_db_session.get(KBSource, int(source_resp.json()["source_id"]))
    assert source is not None
    assert source.account_id == account.id
    assert source.portal_id == portal_a.id
    upload_job = test_db_session.get(KBJob, int(upload_resp.json()["job_id"]))
    assert upload_job is not None
    assert upload_job.account_id == account.id
    source_job = test_db_session.get(KBJob, int(source_resp.json()["job_id"]))
    assert source_job is not None
    assert source_job.account_id == account.id

    assert collection_resp.status_code == 200
    collection = test_db_session.get(KBCollection, int(collection_resp.json()["id"]))
    assert collection is not None
    assert collection.portal_id == portal_a.id
    assert collection.account_id == account.id

    assert folder_resp.status_code == 200
    folder = test_db_session.get(KBSmartFolder, int(folder_resp.json()["id"]))
    assert folder is not None
    assert folder.portal_id == portal_a.id
    assert folder.account_id == account.id


@pytest.mark.timeout(10)
def test_bitrix_topics_are_account_scoped_from_second_portal(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)

    file_rec = KBFile(
        account_id=account.id,
        portal_id=portal_a.id,
        filename="vacation-policy.pdf",
        storage_path="/tmp/vacation-policy.pdf",
        mime_type="application/pdf",
        status="ready",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    folder = KBSmartFolder(
        account_id=account.id,
        portal_id=portal_a.id,
        name="Отпуска",
        system_tag="hr_docs",
        rules_json={"topic": "hr"},
        created_at=datetime.utcnow(),
    )
    test_db_session.add_all([file_rec, folder])
    test_db_session.flush()
    test_db_session.add(
        KBChunk(
            account_id=account.id,
            portal_id=portal_a.id,
            file_id=file_rec.id,
            chunk_index=0,
            text="Онбординг сотрудника и обучение команды в компании",
            page_num=1,
            created_at=datetime.utcnow(),
        )
    )
    test_db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    original_require_admin = bitrix_router._require_portal_admin
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    try:
        resp = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/topics",
            headers={"Authorization": "Bearer tok"},
        )
    finally:
        bitrix_router._require_portal_admin = original_require_admin
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert resp.status_code == 200
    payload = resp.json()
    assert any(int(item["count"]) >= 1 for item in payload.get("topics", []))


@pytest.mark.timeout(10)
def test_bitrix_reindex_all_is_account_scoped_from_second_portal(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)
    file_rec = KBFile(
        account_id=account.id,
        portal_id=portal_a.id,
        filename="shared.txt",
        audience="staff",
        mime_type="text/plain",
        size_bytes=10,
        storage_path="/tmp/shared.txt",
        status="uploaded",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    test_db_session.add(file_rec)
    test_db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    original_require_admin = bitrix_router._require_portal_admin
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    try:
        resp = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/kb/reindex",
            headers={"Authorization": "Bearer tok"},
        )
    finally:
        bitrix_router._require_portal_admin = original_require_admin
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert resp.status_code == 200
    assert int(resp.json()["queued"]) == 1


@pytest.mark.timeout(10)
def test_bitrix_folder_crud_and_file_move_work_across_account_scope(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)
    file_rec = KBFile(
        account_id=account.id,
        portal_id=portal_a.id,
        filename="shared.txt",
        audience="staff",
        mime_type="text/plain",
        size_bytes=10,
        storage_path="/tmp/shared.txt",
        status="ready",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    test_db_session.add(file_rec)
    test_db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    original_require_admin = bitrix_router._require_portal_admin
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    try:
        create_root = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/kb/folders",
            headers={"Authorization": "Bearer tok"},
            json={"name": "Dept"},
        )
        root_id = int(create_root.json()["id"])
        create_child = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/kb/folders",
            headers={"Authorization": "Bearer tok"},
            json={"name": "Policies", "parent_id": root_id},
        )
        child_id = int(create_child.json()["id"])
        move_resp = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/kb/files/{file_rec.id}/folder",
            headers={"Authorization": "Bearer tok"},
            json={"folder_id": child_id},
        )
        list_resp = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/folders",
            headers={"Authorization": "Bearer tok"},
        )
    finally:
        bitrix_router._require_portal_admin = original_require_admin
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert create_root.status_code == 200
    assert create_child.status_code == 200
    assert move_resp.status_code == 200
    assert list_resp.status_code == 200

    root = test_db_session.get(KBFolder, root_id)
    child = test_db_session.get(KBFolder, child_id)
    moved_file = test_db_session.get(KBFile, file_rec.id)
    assert root is not None and child is not None and moved_file is not None
    assert root.account_id == account.id
    assert child.account_id == account.id
    assert root.portal_id == portal_a.id
    assert child.portal_id == portal_a.id
    assert child.parent_id == root.id
    assert moved_file.folder_id == child.id


@pytest.mark.timeout(10)
def test_bitrix_folder_list_exposes_space_roots_and_space_metadata(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)
    client_root = KBFolder(
        account_id=account.id,
        portal_id=portal_a.id,
        name="Клиенты",
        root_space="clients",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    test_db_session.add(client_root)
    test_db_session.flush()
    child = KBFolder(
        account_id=account.id,
        portal_id=portal_a.id,
        parent_id=client_root.id,
        name="Acme",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    test_db_session.add(child)
    test_db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    original_require_admin = bitrix_router._require_portal_admin
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    try:
        resp = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/folders",
            headers={"Authorization": "Bearer tok"},
        )
    finally:
        bitrix_router._require_portal_admin = original_require_admin
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert resp.status_code == 200
    items = resp.json()["items"]
    roots = {item["root_space"] for item in items if item.get("is_space_root")}
    assert {"shared", "departments", "clients"}.issubset(roots)
    child_payload = next(item for item in items if int(item["id"]) == child.id)
    assert child_payload["root_space"] == "clients"
    assert child_payload["is_space_root"] is False


@pytest.mark.timeout(10)
def test_bitrix_space_root_folder_cannot_be_deleted_or_renamed(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)
    root = KBFolder(
        account_id=account.id,
        portal_id=portal_a.id,
        name="Отделы",
        root_space="departments",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    test_db_session.add(root)
    test_db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    original_require_admin = bitrix_router._require_portal_admin
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    try:
        patch_resp = client.patch(
            f"/v1/bitrix/portals/{portal_b.id}/kb/folders/{root.id}",
            headers={"Authorization": "Bearer tok"},
            json={"name": "New name"},
        )
        delete_resp = client.delete(
            f"/v1/bitrix/portals/{portal_b.id}/kb/folders/{root.id}",
            headers={"Authorization": "Bearer tok"},
        )
    finally:
        bitrix_router._require_portal_admin = original_require_admin
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert patch_resp.status_code == 409
    assert delete_resp.status_code == 409


@pytest.mark.timeout(10)
def test_bitrix_folder_delete_blocks_non_empty_folder(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)
    folder = KBFolder(account_id=account.id, portal_id=portal_a.id, name="Dept", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
    test_db_session.add(folder)
    test_db_session.flush()
    test_db_session.add(
        KBFile(
            account_id=account.id,
            portal_id=portal_a.id,
            folder_id=folder.id,
            filename="shared.txt",
            audience="staff",
            mime_type="text/plain",
            size_bytes=10,
            storage_path="/tmp/shared.txt",
            status="ready",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    )
    test_db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    original_require_admin = bitrix_router._require_portal_admin
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    try:
        resp = client.delete(
            f"/v1/bitrix/portals/{portal_b.id}/kb/folders/{folder.id}",
            headers={"Authorization": "Bearer tok"},
        )
    finally:
        bitrix_router._require_portal_admin = original_require_admin
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert resp.status_code == 409


@pytest.mark.timeout(10)
def test_bitrix_folder_and_file_acl_api_and_effective_preview(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)
    folder = KBFolder(account_id=account.id, portal_id=portal_a.id, name="Dept", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
    test_db_session.add(folder)
    test_db_session.flush()
    file_rec = KBFile(
        account_id=account.id,
        portal_id=portal_a.id,
        folder_id=folder.id,
        filename="shared.txt",
        audience="staff",
        mime_type="text/plain",
        size_bytes=10,
        storage_path="/tmp/shared.txt",
        status="ready",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    test_db_session.add(file_rec)
    test_db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    original_require_admin = bitrix_router._require_portal_admin
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    try:
        put_folder = client.put(
            f"/v1/bitrix/portals/{portal_b.id}/kb/folders/{folder.id}/access",
            headers={"Authorization": "Bearer tok"},
            json={"items": [{"principal_type": "role", "principal_id": "member", "access_level": "read"}]},
        )
        put_file = client.put(
            f"/v1/bitrix/portals/{portal_b.id}/kb/files/{file_rec.id}/access",
            headers={"Authorization": "Bearer tok"},
            json={"items": [{"principal_type": "membership", "principal_id": "42", "access_level": "edit"}]},
        )
        get_folder = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/folders/{folder.id}/access",
            headers={"Authorization": "Bearer tok"},
        )
        get_file = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/files/{file_rec.id}/access",
            headers={"Authorization": "Bearer tok"},
        )
        preview = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/files/{file_rec.id}/access/effective?membership_id=42&role=member&audience=client",
            headers={"Authorization": "Bearer tok"},
        )
    finally:
        bitrix_router._require_portal_admin = original_require_admin
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert put_folder.status_code == 200
    assert put_file.status_code == 200
    assert get_folder.status_code == 200
    assert get_file.status_code == 200
    assert preview.status_code == 200
    assert test_db_session.query(KBFolderAccess).filter(KBFolderAccess.folder_id == folder.id).count() == 1
    assert test_db_session.query(KBFileAccess).filter(KBFileAccess.file_id == file_rec.id).count() == 1
    assert preview.json()["folder_access"] == "read"
    assert preview.json()["effective_access"] == "edit"


@pytest.mark.timeout(10)
def test_bitrix_search_respects_file_acl_and_revoke(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)
    file_rec = KBFile(
        account_id=account.id,
        portal_id=portal_a.id,
        filename="restricted.txt",
        audience="staff",
        mime_type="text/plain",
        size_bytes=10,
        storage_path="/tmp/restricted.txt",
        status="ready",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    test_db_session.add(file_rec)
    test_db_session.flush()
    test_db_session.add(
        KBChunk(
            account_id=account.id,
            portal_id=portal_a.id,
            file_id=file_rec.id,
            audience="staff",
            chunk_index=0,
            text="restricted handbook document",
        )
    )
    test_db_session.add(
        KBFileAccess(file_id=file_rec.id, principal_type="membership", principal_id="99", access_level="read")
    )
    test_db_session.commit()

    original_acl_ctx = bitrix_router._portal_acl_subject_ctx
    bitrix_router._portal_acl_subject_ctx = lambda db, portal_id, request, audience: {
        "membership_id": 42,
        "role": "member",
        "audience": audience,
    }
    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    try:
        denied = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/search?q=restricted&limit=20",
            headers={"Authorization": "Bearer tok"},
        )
        assert denied.status_code == 200
        assert denied.json()["file_ids"] == []

        test_db_session.add(
            KBFileAccess(file_id=file_rec.id, principal_type="membership", principal_id="42", access_level="read")
        )
        test_db_session.commit()

        allowed = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/search?q=restricted&limit=20",
            headers={"Authorization": "Bearer tok"},
        )
        assert allowed.status_code == 200
        assert allowed.json()["file_ids"] == [file_rec.id]

        test_db_session.query(KBFileAccess).filter(
            KBFileAccess.file_id == file_rec.id,
            KBFileAccess.principal_id == "42",
        ).delete()
        test_db_session.commit()

        revoked = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/search?q=restricted&limit=20",
            headers={"Authorization": "Bearer tok"},
        )
        assert revoked.status_code == 200
        assert revoked.json()["file_ids"] == []
    finally:
        bitrix_router._portal_acl_subject_ctx = original_acl_ctx
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)


@pytest.mark.timeout(10)
def test_bitrix_search_respects_group_acl(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)
    app_user = AppUser(display_name="Sales User", status="active")
    test_db_session.add(app_user)
    test_db_session.flush()
    membership = AccountMembership(account_id=account.id, user_id=app_user.id, role="member", status="active")
    test_db_session.add(membership)
    test_db_session.flush()

    group = AccountUserGroup(account_id=account.id, name="Sales")
    test_db_session.add(group)
    test_db_session.flush()
    test_db_session.add(AccountUserGroupMember(group_id=group.id, membership_id=membership.id))

    integration = test_db_session.execute(
        select(AccountIntegration).where(
            AccountIntegration.account_id == account.id,
            AccountIntegration.provider == "bitrix",
            AccountIntegration.portal_id == portal_b.id,
        )
    ).scalar_one()
    test_db_session.add(
        AppUserIdentity(
            user_id=app_user.id,
            provider="bitrix",
            integration_id=integration.id,
            external_id="77",
            display_value="Sales User",
            created_at=datetime.utcnow(),
        )
    )

    file_rec = KBFile(
        account_id=account.id,
        portal_id=portal_a.id,
        filename="sales.txt",
        audience="staff",
        mime_type="text/plain",
        size_bytes=10,
        storage_path="/tmp/sales.txt",
        status="ready",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    test_db_session.add(file_rec)
    test_db_session.flush()
    test_db_session.add(
        KBChunk(
            account_id=account.id,
            portal_id=portal_a.id,
            file_id=file_rec.id,
            audience="staff",
            chunk_index=0,
            text="sales handbook document",
        )
    )
    test_db_session.add(
        KBFileAccess(file_id=file_rec.id, principal_type="group", principal_id=str(group.id), access_level="read")
    )
    test_db_session.commit()

    original_decode = bitrix_router.decode_token
    bitrix_router.decode_token = lambda token: {"uid": 77}
    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    try:
        allowed = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/search?q=sales&limit=20",
            headers={"Authorization": "Bearer group-token"},
        )
        assert allowed.status_code == 200
        assert allowed.json()["file_ids"] == [file_rec.id]

        test_db_session.query(AccountUserGroupMember).filter(
            AccountUserGroupMember.group_id == group.id,
            AccountUserGroupMember.membership_id == membership.id,
        ).delete()
        test_db_session.commit()

        revoked = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/search?q=sales&limit=20",
            headers={"Authorization": "Bearer group-token"},
        )
        assert revoked.status_code == 200
        assert revoked.json()["file_ids"] == []
    finally:
        bitrix_router.decode_token = original_decode
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)


@pytest.mark.timeout(10)
def test_bitrix_client_search_respects_client_group_acl(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)
    app_user = AppUser(display_name="Client User", status="active")
    test_db_session.add(app_user)
    test_db_session.flush()
    membership = AccountMembership(account_id=account.id, user_id=app_user.id, role="client", status="active")
    test_db_session.add(membership)
    test_db_session.flush()

    group = AccountUserGroup(account_id=account.id, name="Acme Clients", kind="client")
    test_db_session.add(group)
    test_db_session.flush()
    test_db_session.add(AccountUserGroupMember(group_id=group.id, membership_id=membership.id))

    integration = test_db_session.execute(
        select(AccountIntegration).where(
            AccountIntegration.account_id == account.id,
            AccountIntegration.provider == "bitrix",
            AccountIntegration.portal_id == portal_b.id,
        )
    ).scalar_one()
    test_db_session.add(
        AppUserIdentity(
            user_id=app_user.id,
            provider="bitrix",
            integration_id=integration.id,
            external_id="701",
            display_value="Client User",
            created_at=datetime.utcnow(),
        )
    )

    file_rec = KBFile(
        account_id=account.id,
        portal_id=portal_a.id,
        filename="client-group.txt",
        audience="client",
        mime_type="text/plain",
        size_bytes=10,
        storage_path="/tmp/client-group.txt",
        status="ready",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    test_db_session.add(file_rec)
    test_db_session.flush()
    test_db_session.add(
        KBChunk(
            account_id=account.id,
            portal_id=portal_a.id,
            file_id=file_rec.id,
            audience="client",
            chunk_index=0,
            text="client contract handbook",
        )
    )
    test_db_session.add(
        KBFileAccess(file_id=file_rec.id, principal_type="group", principal_id=str(group.id), access_level="read")
    )
    test_db_session.commit()

    original_decode = bitrix_router.decode_token
    bitrix_router.decode_token = lambda token: {"uid": 701}
    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    try:
        allowed = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/search?q=client&limit=20&audience=client",
            headers={"Authorization": "Bearer client-group-token"},
        )
        assert allowed.status_code == 200
        assert allowed.json()["file_ids"] == [file_rec.id]

        test_db_session.query(AccountUserGroupMember).filter(
            AccountUserGroupMember.group_id == group.id,
            AccountUserGroupMember.membership_id == membership.id,
        ).delete()
        test_db_session.commit()

        revoked = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/search?q=client&limit=20&audience=client",
            headers={"Authorization": "Bearer client-group-token"},
        )
        assert revoked.status_code == 200
        assert revoked.json()["file_ids"] == []
    finally:
        bitrix_router.decode_token = original_decode
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)


@pytest.mark.timeout(10)
def test_bitrix_ask_respects_file_acl_scope(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)
    file_rec = KBFile(
        account_id=account.id,
        portal_id=portal_a.id,
        filename="client-only.txt",
        audience="staff",
        mime_type="text/plain",
        size_bytes=10,
        storage_path="/tmp/client-only.txt",
        status="ready",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    test_db_session.add(file_rec)
    test_db_session.commit()
    test_db_session.add(
        KBFileAccess(file_id=file_rec.id, principal_type="membership", principal_id="99", access_level="read")
    )
    test_db_session.commit()

    captured: dict[str, object] = {}
    original_answer_from_kb = bitrix_router.answer_from_kb
    original_acl_ctx = bitrix_router._portal_acl_subject_ctx

    def _fake_answer_from_kb(db, portal_id, query, **kwargs):
        captured["file_ids_filter"] = kwargs.get("file_ids_filter")
        return "ok", None, {}

    bitrix_router.answer_from_kb = _fake_answer_from_kb
    bitrix_router._portal_acl_subject_ctx = lambda db, portal_id, request, audience: {
        "membership_id": 42,
        "role": "member",
        "audience": audience,
    }
    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    try:
        denied = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/kb/ask",
            headers={"Authorization": "Bearer tok"},
            json={"query": "test"},
        )
        assert denied.status_code == 200
        assert "file_ids_filter" not in captured
        assert "материал" in denied.json()["answer"].lower()

        test_db_session.add(
            KBFileAccess(file_id=file_rec.id, principal_type="membership", principal_id="42", access_level="read")
        )
        test_db_session.commit()

        allowed = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/kb/ask",
            headers={"Authorization": "Bearer tok"},
            json={"query": "test"},
        )
        assert allowed.status_code == 200
        assert captured["file_ids_filter"] == [file_rec.id]
    finally:
        bitrix_router.answer_from_kb = original_answer_from_kb
        bitrix_router._portal_acl_subject_ctx = original_acl_ctx
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)


@pytest.mark.timeout(10)
def test_bitrix_client_ask_respects_client_group_acl_scope(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)
    app_user = AppUser(display_name="Client Ask", status="active")
    test_db_session.add(app_user)
    test_db_session.flush()
    membership = AccountMembership(account_id=account.id, user_id=app_user.id, role="client", status="active")
    test_db_session.add(membership)
    test_db_session.flush()
    group = AccountUserGroup(account_id=account.id, name="Client Ask Group", kind="client")
    test_db_session.add(group)
    test_db_session.flush()
    test_db_session.add(AccountUserGroupMember(group_id=group.id, membership_id=membership.id))

    integration = test_db_session.execute(
        select(AccountIntegration).where(
            AccountIntegration.account_id == account.id,
            AccountIntegration.provider == "bitrix",
            AccountIntegration.portal_id == portal_b.id,
        )
    ).scalar_one()
    test_db_session.add(
        AppUserIdentity(
            user_id=app_user.id,
            provider="bitrix",
            integration_id=integration.id,
            external_id="702",
            display_value="Client Ask",
            created_at=datetime.utcnow(),
        )
    )

    file_rec = KBFile(
        account_id=account.id,
        portal_id=portal_a.id,
        filename="client-scope.txt",
        audience="client",
        mime_type="text/plain",
        size_bytes=10,
        storage_path="/tmp/client-scope.txt",
        status="ready",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    test_db_session.add(file_rec)
    test_db_session.flush()
    test_db_session.add(
        KBFileAccess(file_id=file_rec.id, principal_type="group", principal_id=str(group.id), access_level="read")
    )
    test_db_session.commit()

    captured: dict[str, object] = {}
    original_answer_from_kb = bitrix_router.answer_from_kb
    original_acl_ctx = bitrix_router._portal_acl_subject_ctx

    def _fake_answer_from_kb(db, portal_id, query, **kwargs):
        captured["file_ids_filter"] = kwargs.get("file_ids_filter")
        return "ok", None, {}

    bitrix_router.answer_from_kb = _fake_answer_from_kb
    bitrix_router._portal_acl_subject_ctx = lambda db, portal_id, request, audience: {
        "membership_id": membership.id,
        "group_ids": [group.id],
        "role": "client",
        "audience": audience,
        "portal_user_id": 702,
    }
    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    try:
        allowed = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/kb/ask",
            headers={"Authorization": "Bearer client-ask-token"},
            json={"query": "client", "audience": "client"},
        )
        assert allowed.status_code == 200
        assert captured["file_ids_filter"] == [file_rec.id]

        test_db_session.query(AccountUserGroupMember).filter(
            AccountUserGroupMember.group_id == group.id,
            AccountUserGroupMember.membership_id == membership.id,
        ).delete()
        test_db_session.commit()
        captured.clear()
        bitrix_router._portal_acl_subject_ctx = lambda db, portal_id, request, audience: {
            "membership_id": membership.id,
            "group_ids": [],
            "role": "client",
            "audience": audience,
            "portal_user_id": 702,
        }

        denied = client.post(
            f"/v1/bitrix/portals/{portal_b.id}/kb/ask",
            headers={"Authorization": "Bearer client-ask-token"},
            json={"query": "client", "audience": "client"},
        )
        assert denied.status_code == 200
        assert "file_ids_filter" not in captured
    finally:
        bitrix_router.answer_from_kb = original_answer_from_kb
        bitrix_router._portal_acl_subject_ctx = original_acl_ctx
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)


@pytest.mark.timeout(10)
def test_bitrix_file_browsing_surfaces_respect_acl(test_db_session):
    account, portal_a, portal_b = _seed_account_with_two_portals(test_db_session)
    collection = KBCollection(
        account_id=account.id,
        portal_id=portal_a.id,
        name="Restricted set",
        created_at=datetime.utcnow(),
    )
    test_db_session.add(collection)
    test_db_session.flush()
    file_rec = KBFile(
        account_id=account.id,
        portal_id=portal_a.id,
        filename="topic-policy.txt",
        audience="staff",
        mime_type="text/plain",
        size_bytes=10,
        storage_path=__file__,
        status="ready",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    test_db_session.add(file_rec)
    test_db_session.flush()
    test_db_session.add(KBCollectionFile(collection_id=collection.id, file_id=file_rec.id, created_at=datetime.utcnow()))
    test_db_session.add(
        KBChunk(
            account_id=account.id,
            portal_id=portal_a.id,
            file_id=file_rec.id,
            audience="staff",
            chunk_index=0,
            text="billing contract pricing access",
        )
    )
    test_db_session.add(
        KBFileAccess(file_id=file_rec.id, principal_type="membership", principal_id="99", access_level="read")
    )
    test_db_session.commit()

    original_acl_ctx = bitrix_router._portal_acl_subject_ctx
    original_require_admin = bitrix_router._require_portal_admin
    bitrix_router._portal_acl_subject_ctx = lambda db, portal_id, request, audience: {
        "membership_id": 42,
        "role": "member",
        "audience": audience,
    }
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal_b.id
    try:
        files_denied = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/files",
            headers={"Authorization": "Bearer tok"},
        )
        collection_denied = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/collections/{collection.id}/files",
            headers={"Authorization": "Bearer tok"},
        )
        topics_denied = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/topics",
            headers={"Authorization": "Bearer tok"},
        )
        download_denied = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/files/{file_rec.id}/download",
            headers={"Authorization": "Bearer tok"},
        )

        assert files_denied.status_code == 200
        assert files_denied.json()["items"] == []
        assert collection_denied.status_code == 200
        assert collection_denied.json()["file_ids"] == []
        assert download_denied.status_code == 404
        denied_topic_ids = {item["id"] for item in topics_denied.json()["topics"] if item["count"] > 0}
        assert denied_topic_ids == set()

        test_db_session.add(
            KBFileAccess(file_id=file_rec.id, principal_type="membership", principal_id="42", access_level="read")
        )
        test_db_session.commit()

        files_allowed = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/files",
            headers={"Authorization": "Bearer tok"},
        )
        collection_allowed = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/collections/{collection.id}/files",
            headers={"Authorization": "Bearer tok"},
        )
        download_allowed = client.get(
            f"/v1/bitrix/portals/{portal_b.id}/kb/files/{file_rec.id}/download",
            headers={"Authorization": "Bearer tok"},
        )

        assert files_allowed.status_code == 200
        assert [item["id"] for item in files_allowed.json()["items"]] == [file_rec.id]
        assert collection_allowed.status_code == 200
        assert collection_allowed.json()["file_ids"] == [file_rec.id]
        assert download_allowed.status_code == 200
    finally:
        bitrix_router._portal_acl_subject_ctx = original_acl_ctx
        bitrix_router._require_portal_admin = original_require_admin
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)


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
