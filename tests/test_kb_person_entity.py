from apps.backend.services.kb_rag import _extract_person_entity_answer


def test_person_answer_prefers_exact_surname_match():
    query = "кто такой алексей лагутин"
    chunks = [
        {"text": "Алексей Федоров — специалист по автоматизации документооборота."},
        {"text": "Алексей Лагутин — ex-руководитель направления продаж и внедрений Mango Office."},
    ]

    out = _extract_person_entity_answer(query, chunks)

    assert out is not None
    assert "Лагутин" in out
    assert "Федоров" not in out


def test_person_answer_returns_insufficient_without_surname_evidence():
    query = "кто такой алексей лагутин"
    chunks = [
        {"text": "Алексей Федоров — специалист по автоматизации документооборота."},
        {"text": "Алексей Иванов — руководитель проектов."},
    ]

    out = _extract_person_entity_answer(query, chunks)

    assert out == "В базе знаний нет подтвержденной информации по этому человеку."
