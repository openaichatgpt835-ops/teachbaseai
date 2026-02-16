"""KB search and ask endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from apps.backend.main import app
from apps.backend.deps import get_db
from apps.backend.database import get_test_engine, Base
from apps.backend.models.portal import Portal
from apps.backend.models.kb import KBFile, KBChunk
from apps.backend.models.kb import KBEmbedding
from apps.backend.services.kb_rag import answer_from_kb
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


@pytest.mark.timeout(10)
def test_kb_search_returns_file_ids(test_db_session, override_get_db):
    portal = Portal(domain="test.bitrix24.ru", status="active", admin_user_id=1)
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)

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
        text="Это документ про тарифы и цены",
    )
    test_db_session.add(c)
    test_db_session.commit()

    portal_token = create_portal_token_with_user(portal.id, user_id=1, expires_minutes=10)

    app.dependency_overrides[get_db] = override_get_db
    try:
        r = client.get(
            f"/v1/bitrix/portals/{portal.id}/kb/search?q=тарифы&limit=10",
            headers={"Authorization": f"Bearer {portal_token}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    data = r.json()
    assert f.id in data.get("file_ids", [])
    matches = data.get("matches", [])
    assert any(m.get("file_id") == f.id for m in matches)


@pytest.mark.timeout(10)
def test_kb_ask_returns_answer(test_db_session, override_get_db):
    portal = Portal(domain="test.bitrix24.ru", status="active", admin_user_id=1)
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)

    portal_token = create_portal_token_with_user(portal.id, user_id=1, expires_minutes=10)

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("apps.backend.routers.bitrix.answer_from_kb", return_value=("ok", None, None)):
            r = client.post(
                f"/v1/bitrix/portals/{portal.id}/kb/ask",
                headers={"Authorization": f"Bearer {portal_token}"},
                json={"query": "Какие тарифы?"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    assert r.json().get("answer") == "ok"


@pytest.mark.timeout(10)
def test_kb_files_include_query_count(test_db_session, override_get_db):
    portal = Portal(domain="test.bitrix24.ru", status="active", admin_user_id=1)
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)

    f = KBFile(
        portal_id=portal.id,
        filename="manual.pdf",
        audience="staff",
        mime_type="application/pdf",
        size_bytes=10,
        storage_path="/tmp/manual.pdf",
        status="ready",
        query_count=3,
    )
    test_db_session.add(f)
    test_db_session.commit()

    portal_token = create_portal_token_with_user(portal.id, user_id=1, expires_minutes=10)

    app.dependency_overrides[get_db] = override_get_db
    try:
        r = client.get(
            f"/v1/bitrix/portals/{portal.id}/kb/files",
            headers={"Authorization": f"Bearer {portal_token}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    data = r.json()
    item = next((x for x in data.get("items", []) if x["id"] == f.id), None)
    assert item is not None
    assert item.get("query_count") == 3


@pytest.mark.timeout(10)
def test_kb_rag_increments_query_count(test_db_session, override_get_db):
    portal = Portal(domain="test.bitrix24.ru", status="active", admin_user_id=1)
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)

    f = KBFile(
        portal_id=portal.id,
        filename="faq.txt",
        audience="staff",
        mime_type="text/plain",
        size_bytes=10,
        storage_path="/tmp/faq.txt",
        status="ready",
        query_count=0,
    )
    test_db_session.add(f)
    test_db_session.commit()
    test_db_session.refresh(f)

    c = KBChunk(
        portal_id=portal.id,
        file_id=f.id,
        audience="staff",
        chunk_index=0,
        text="Ответы на вопросы о тарифах",
    )
    test_db_session.add(c)
    test_db_session.commit()
    test_db_session.refresh(c)

    emb = KBEmbedding(chunk_id=c.id, vector_json=[0.1, 0.2, 0.3], model="EmbeddingsGigaR")
    test_db_session.add(emb)
    test_db_session.commit()

    with patch("apps.backend.services.kb_rag.get_valid_gigachat_access_token", return_value=("token", None)), \
         patch("apps.backend.services.kb_rag.create_embeddings", return_value=([[0.1, 0.2, 0.3]], None, None)), \
         patch("apps.backend.services.kb_rag.chat_complete", return_value=("ok", None, None)):
        answer, err, _usage = answer_from_kb(test_db_session, portal.id, "Тарифы", audience="staff")

    assert err is None
    assert answer is not None
    test_db_session.refresh(f)
    assert f.query_count == 1
