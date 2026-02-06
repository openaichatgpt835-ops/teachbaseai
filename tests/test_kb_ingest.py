"""KB ingest tests."""
import pytest
from sqlalchemy.orm import sessionmaker

from apps.backend.database import get_test_engine, Base
from apps.backend.models.kb import KBFile, KBChunk, KBEmbedding
from apps.backend.services.kb_ingest import ingest_file, chunk_text
from apps.backend.services.kb_settings import set_gigachat_settings


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


@pytest.mark.timeout(10)
def test_chunk_text_basic():
    text = "abc " * 500
    chunks = chunk_text(text, max_chars=200, overlap=50)
    assert chunks
    assert all(len(c) <= 200 for c in chunks)


@pytest.mark.timeout(10)
def test_ingest_csv_creates_chunks_and_embeddings(tmp_path, test_db_session, monkeypatch):
    p = tmp_path / "test.csv"
    p.write_text("col1,col2\nhello,world\n", encoding="utf-8")

    set_gigachat_settings(
        test_db_session,
        api_base="https://gigachat.devices.sberbank.ru/api/v1",
        model="test-emb",
        client_id=None,
        auth_key="key",
        scope="GIGACHAT_API_PERS",
        client_secret=None,
        access_token=None,
    )

    def fake_get_valid_token(db):
        return "token", None

    def fake_create_embeddings(api_base, access_token, model, texts):
        return [[0.1, 0.2, 0.3] for _ in texts], None

    monkeypatch.setattr("apps.backend.services.kb_ingest.get_valid_gigachat_access_token", fake_get_valid_token)
    monkeypatch.setattr("apps.backend.services.kb_ingest.create_embeddings", fake_create_embeddings)

    rec = KBFile(
        portal_id=1,
        filename="test.csv",
        mime_type="text/csv",
        size_bytes=10,
        storage_path=str(p),
        sha256="x",
        status="uploaded",
    )
    test_db_session.add(rec)
    test_db_session.commit()
    test_db_session.refresh(rec)

    res = ingest_file(test_db_session, rec.id)
    assert res.get("ok") is True
    assert test_db_session.query(KBChunk).count() > 0
    assert test_db_session.query(KBEmbedding).count() > 0
