"""Dual mode response schema tests (legacy + v2)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from apps.backend.main import app
from apps.backend.deps import get_db
from apps.backend.database import Base, get_test_engine
from apps.backend.models.portal import Portal
from apps.backend.models.kb import KBFile, KBChunk
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


def _portal_and_token(db):
    portal = Portal(domain="dual.bitrix24.ru", status="active", admin_user_id=1)
    db.add(portal)
    db.commit()
    db.refresh(portal)
    token = create_portal_token_with_user(portal.id, user_id=1, expires_minutes=10)
    return portal, token


@pytest.mark.timeout(10)
def test_kb_ask_legacy_schema_default(test_db_session, override_get_db):
    portal, portal_token = _portal_and_token(test_db_session)
    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("apps.backend.routers.bitrix.answer_from_kb", return_value=("ok", None, None)):
            r = client.post(
                f"/v1/bitrix/portals/{portal.id}/kb/ask",
                headers={"Authorization": f"Bearer {portal_token}"},
                json={"query": "test"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    data = r.json()
    assert data.get("answer") == "ok"
    assert "ok" not in data


@pytest.mark.timeout(10)
def test_kb_ask_v2_schema_header(test_db_session, override_get_db):
    portal, portal_token = _portal_and_token(test_db_session)
    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("apps.backend.routers.bitrix.answer_from_kb", return_value=("ok", None, None)):
            r = client.post(
                f"/v1/bitrix/portals/{portal.id}/kb/ask",
                headers={
                    "Authorization": f"Bearer {portal_token}",
                    "X-Api-Schema": "v2",
                },
                json={"query": "test"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert data.get("data", {}).get("answer") == "ok"
    assert data.get("meta", {}).get("schema") == "v2"


@pytest.mark.timeout(10)
def test_botflow_test_v2_schema_header(test_db_session, override_get_db):
    portal, portal_token = _portal_and_token(test_db_session)
    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch(
            "apps.backend.routers.bitrix_botflow.execute_client_flow_preview",
            return_value=("reply", {"vars": {}}, [{"event": "node"}]),
        ):
            r = client.post(
                f"/v1/bitrix/portals/{portal.id}/botflow/client/test",
                headers={
                    "Authorization": f"Bearer {portal_token}",
                    "X-Api-Schema": "v2",
                },
                json={"text": "hello", "draft_json": {"nodes": [], "edges": []}},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert data.get("data", {}).get("answer") == "reply"
    assert data.get("data", {}).get("trace") == [{"event": "node"}]
    assert data.get("meta", {}).get("schema") == "v2"


@pytest.mark.timeout(10)
def test_kb_search_v2_schema_header(test_db_session, override_get_db):
    portal, portal_token = _portal_and_token(test_db_session)
    f = KBFile(
        portal_id=portal.id,
        filename="services.docx",
        audience="staff",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=10,
        storage_path="/tmp/services.docx",
        status="ready",
    )
    test_db_session.add(f)
    test_db_session.commit()
    test_db_session.refresh(f)
    c = KBChunk(
        portal_id=portal.id,
        file_id=f.id,
        audience="staff",
        chunk_index=0,
        text="Тарифы и цены",
    )
    test_db_session.add(c)
    test_db_session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        r = client.get(
            f"/v1/bitrix/portals/{portal.id}/kb/search?q=Тарифы",
            headers={
                "Authorization": f"Bearer {portal_token}",
                "X-Api-Schema": "v2",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert f.id in data.get("data", {}).get("file_ids", [])
    assert data.get("meta", {}).get("schema") == "v2"
