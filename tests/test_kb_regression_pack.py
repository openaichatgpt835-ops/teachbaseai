from unittest.mock import patch

import pytest
from sqlalchemy.orm import sessionmaker

from apps.backend.database import Base, get_test_engine
from apps.backend.models.kb import KBChunk, KBEmbedding, KBFile
from apps.backend.models.portal import Portal
from apps.backend.services.kb_rag import answer_from_kb


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


def _make_portal(db):
    portal = Portal(domain="eval.bitrix24.ru", status="active", admin_user_id=1)
    db.add(portal)
    db.commit()
    db.refresh(portal)
    return portal


def _add_ready_file(db, portal_id: int, filename: str, text: str):
    f = KBFile(
        portal_id=portal_id,
        filename=filename,
        audience="staff",
        mime_type="text/plain",
        size_bytes=10,
        storage_path=f"/tmp/{filename}",
        status="ready",
        query_count=0,
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    c = KBChunk(
        portal_id=portal_id,
        file_id=f.id,
        audience="staff",
        chunk_index=0,
        text=text,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    emb = KBEmbedding(chunk_id=c.id, vector_json=[0.1, 0.2, 0.3], model="EmbeddingsGigaR")
    db.add(emb)
    db.commit()
    return f, c


@pytest.mark.timeout(10)
def test_regression_pack_simple_arithmetic_shortcut(test_db_session):
    portal = _make_portal(test_db_session)
    answer, err, usage = answer_from_kb(test_db_session, portal.id, "сколько будет три плюс два", audience="staff")
    assert err is None
    assert answer == "Ответ: 5"
    assert usage is not None
    assert usage.get("evidence_count") == 0


@pytest.mark.timeout(10)
def test_regression_pack_numeric_query_ignores_irrelevant_numbers(test_db_session):
    portal = _make_portal(test_db_session)
    _add_ready_file(
        test_db_session,
        portal.id,
        "promo.txt",
        "При заказе до 31 августа вы получите 2 товара по цене 1.",
    )
    with patch("apps.backend.services.kb_rag.get_valid_gigachat_access_token", return_value=("token", None)), \
         patch("apps.backend.services.kb_rag.create_embeddings", return_value=([[0.1, 0.2, 0.3]], None, None)), \
         patch("apps.backend.services.kb_rag.chat_complete", return_value=("ok", None, None)):
        answer, err, _usage = answer_from_kb(test_db_session, portal.id, "сколько жмет спартак", audience="staff")
    assert err is None
    assert answer is not None
    low = answer.lower()
    assert "31 августа" not in low
    assert "2 товара" not in low


@pytest.mark.timeout(10)
def test_regression_pack_instruction_query_stays_product_grounded(test_db_session):
    portal = _make_portal(test_db_session)
    _add_ready_file(
        test_db_session,
        portal.id,
        "manual.txt",
        "Откройте раздел Пользователи и доступы. Выберите сотрудника. Назначьте доступ к базе знаний и сохраните изменения.",
    )

    captured = {}

    def _fake_chat_complete(_api, _token, _model, messages, **kwargs):
        captured["system"] = messages[0]["content"]
        return "1) Откройте раздел Пользователи и доступы. 2) Выберите сотрудника. 3) Назначьте доступ и сохраните изменения.", None, {}

    with patch("apps.backend.services.kb_rag.get_valid_gigachat_access_token", return_value=("token", None)), \
         patch("apps.backend.services.kb_rag.create_embeddings", return_value=([[0.1, 0.2, 0.3]], None, None)), \
         patch("apps.backend.services.kb_rag.chat_complete", side_effect=_fake_chat_complete):
        answer, err, _usage = answer_from_kb(test_db_session, portal.id, "как настроить доступ к базе знаний", audience="staff")

    assert err is None
    assert answer is not None
    assert "не заменяй ответ общими рекомендациями" in captured["system"].lower()
    assert "Пользователи и доступы" in answer


@pytest.mark.timeout(10)
def test_regression_pack_overview_query_uses_context_entities(test_db_session):
    portal = _make_portal(test_db_session)
    _add_ready_file(
        test_db_session,
        portal.id,
        "book.txt",
        (
            "Тави вместе со спутниками пробирается через болота. "
            "Им приходится искать безопасный путь и действовать осторожно. "
            "Позади движется Ливень."
        ),
    )

    with patch("apps.backend.services.kb_rag.get_valid_gigachat_access_token", return_value=("token", None)), \
         patch("apps.backend.services.kb_rag.create_embeddings", return_value=([[0.1, 0.2, 0.3]], None, None)), \
         patch(
             "apps.backend.services.kb_rag.chat_complete",
             return_value=(
                 "Тави вместе со спутниками пробирается через болота и ищет безопасный путь. Позади движется Ливень, поэтому группе приходится действовать осторожно.",
                 None,
                 {},
             ),
         ):
        answer, err, _usage = answer_from_kb(test_db_session, portal.id, "расскажи мне про тави и её спутников", audience="staff")

    assert err is None
    assert answer is not None
    low = answer.lower()
    assert "тави" in low
    assert "спутник" in low
    assert "ливень" in low


@pytest.mark.timeout(10)
def test_regression_pack_skips_lexical_recall_when_pg_hits_are_enough(test_db_session, monkeypatch):
    portal = _make_portal(test_db_session)
    _add_ready_file(
        test_db_session,
        portal.id,
        "guide.txt",
        "Спартак жмет 180 кг и рассказывает о силовых тренировках.",
    )

    calls = {"lexical": 0}

    def _fake_append(*args, **kwargs):
        calls["lexical"] += 1

    monkeypatch.setattr("apps.backend.services.kb_rag._append_lexical_recall_rows", _fake_append)

    with patch("apps.backend.services.kb_rag.get_valid_gigachat_access_token", return_value=("token", None)), \
         patch("apps.backend.services.kb_rag.create_embeddings", return_value=([[0.1, 0.2, 0.3]], None, None)), \
         patch("apps.backend.services.kb_rag.chat_complete", return_value=("Спартак жмет 180 кг.", None, {})):
        answer, err, _usage = answer_from_kb(test_db_session, portal.id, "спартак жмет 180 кг", audience="staff")

    assert err is None
    assert answer is not None
    assert calls["lexical"] == 0
