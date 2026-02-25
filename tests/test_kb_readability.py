from apps.backend.services.kb_rag import _normalize_answer_readability


def test_normalize_answer_readability_splits_long_prose_into_paragraphs():
    src = (
        "Это длинный ответ с несколькими предложениями и дополнительными деталями про процесс внедрения и этапы запуска. "
        "Он должен быть разбит на абзацы для лучшей читаемости и визуального восприятия пользователем в интерфейсе. "
        "Третье предложение тоже должно остаться и не потерять исходный смысл, который был в начальном тексте. "
        "Четвертое предложение завершает мысль и добавляет итоговый акцент на качестве результата."
    )
    out = _normalize_answer_readability(src)

    assert "\n\n" in out
    assert "Это длинный ответ" in out
    assert "Четвертое предложение" in out


def test_normalize_answer_readability_keeps_lists_intact():
    src = "1) Первый пункт.\n2) Второй пункт.\n3) Третий пункт."
    out = _normalize_answer_readability(src)

    assert out.count("\n") == 2
    assert out.startswith("1) Первый пункт")
