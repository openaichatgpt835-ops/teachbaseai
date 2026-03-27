from __future__ import annotations

import importlib.util
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

if importlib.util.find_spec("jose") is None:
    pytest.skip("python-jose is required for API app import in this environment", allow_module_level=True)

from apps.backend.database import Base, get_test_engine
from apps.backend.deps import get_db
from apps.backend.main import app
from apps.backend.models.account import Account
from apps.backend.models.account_kb_setting import AccountKBSetting
from apps.backend.models.billing import AccountSubscription, BillingPlan
from apps.backend.models.portal import Portal
from apps.backend.models.portal_kb_setting import PortalKBSetting
from apps.backend.routers import bitrix as bitrix_router
from apps.backend.services.billing import ensure_base_plans
from apps.backend.services.kb_settings import DEFAULT_CHAT_MODEL, DEFAULT_EMBEDDING_MODEL, get_effective_gigachat_settings


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


def _seed_start_plan(db, account: Account) -> None:
    ensure_base_plans(db)
    start_plan = db.query(BillingPlan).filter(BillingPlan.code == "start").one()
    db.add(
        AccountSubscription(
            account_id=account.id,
            plan_id=start_plan.id,
            status="active",
            started_at=datetime.utcnow(),
        )
    )
    db.commit()


@pytest.mark.timeout(10)
def test_portal_kb_settings_api_applies_tariff_gates(test_db_session):
    account = Account(name="Locked Account", status="active")
    test_db_session.add(account)
    test_db_session.commit()
    test_db_session.refresh(account)
    _seed_start_plan(test_db_session, account)

    portal = Portal(domain="locked-settings.bitrix24.ru", status="active", admin_user_id=1, account_id=account.id)
    test_db_session.add(portal)
    test_db_session.flush()
    test_db_session.add(
        PortalKBSetting(
            portal_id=portal.id,
            embedding_model="CustomEmbedding",
            chat_model="CustomChat",
            media_transcription_enabled=True,
            speaker_diarization_enabled=True,
            temperature=0.9,
            system_prompt_extra="custom prompt",
        )
    )
    test_db_session.commit()

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal.id
    original_require_admin = bitrix_router._require_portal_admin
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    try:
        resp = client.get(f"/v1/bitrix/portals/{portal.id}/kb/settings")
    finally:
        bitrix_router._require_portal_admin = original_require_admin
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["billing_policy"]["plan_code"] == "start"
    assert data["model_selection_available"] is False
    assert data["advanced_tuning_available"] is False
    assert data["media_transcription_available"] is False
    assert data["speaker_diarization_available"] is False
    assert data["media_transcription_enabled"] is False
    assert data["speaker_diarization_enabled"] is False


@pytest.mark.timeout(10)
def test_effective_gigachat_settings_ignores_locked_portal_overrides(test_db_session):
    account = Account(name="Locked Runtime", status="active")
    test_db_session.add(account)
    test_db_session.commit()
    test_db_session.refresh(account)
    _seed_start_plan(test_db_session, account)

    portal = Portal(domain="locked-runtime.bitrix24.ru", status="active", admin_user_id=1, account_id=account.id)
    test_db_session.add(portal)
    test_db_session.flush()
    test_db_session.add(
        PortalKBSetting(
            portal_id=portal.id,
            embedding_model="CustomEmbedding",
            chat_model="CustomChat",
            temperature=0.9,
            max_tokens=999,
            system_prompt_extra="custom prompt",
            media_transcription_enabled=True,
            speaker_diarization_enabled=True,
        )
    )
    test_db_session.commit()

    settings = get_effective_gigachat_settings(test_db_session, portal.id)
    assert settings["embedding_model"] == DEFAULT_EMBEDDING_MODEL
    assert settings["chat_model"] == DEFAULT_CHAT_MODEL
    assert settings["temperature"] == 0.2
    assert settings["max_tokens"] == 700
    assert settings["system_prompt_extra"] == ""
    assert settings["media_transcription_enabled"] is False
    assert settings["speaker_diarization_enabled"] is False


@pytest.mark.timeout(10)
def test_portal_kb_settings_save_clamps_locked_features(test_db_session):
    account = Account(name="Locked Save", status="active")
    test_db_session.add(account)
    test_db_session.commit()
    test_db_session.refresh(account)
    _seed_start_plan(test_db_session, account)

    portal = Portal(domain="locked-save.bitrix24.ru", status="active", admin_user_id=1, account_id=account.id)
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)

    app.dependency_overrides[get_db] = _override_get_db(test_db_session)
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal.id
    original_require_admin = bitrix_router._require_portal_admin
    bitrix_router._require_portal_admin = lambda db, portal_id, request: None
    try:
        save = client.post(
            f"/v1/bitrix/portals/{portal.id}/kb/settings",
            json={
                "embedding_model": "CustomEmbedding",
                "chat_model": "CustomChat",
                "temperature": 0.9,
                "system_prompt_extra": "custom prompt",
                "media_transcription_enabled": True,
                "speaker_diarization_enabled": True,
            },
        )
    finally:
        bitrix_router._require_portal_admin = original_require_admin
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)

    assert save.status_code == 200
    data = save.json()
    assert data["media_transcription_enabled"] is False
    assert data["speaker_diarization_enabled"] is False

    row = test_db_session.get(AccountKBSetting, account.id)
    assert row is not None
    assert row.embedding_model is None
    assert row.chat_model is None
    assert row.temperature is None
    assert row.system_prompt_extra is None
    assert row.media_transcription_enabled is False
    assert row.speaker_diarization_enabled is False
