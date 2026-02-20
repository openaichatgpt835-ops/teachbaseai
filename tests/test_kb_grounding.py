from apps.backend.services.kb_rag import _verify_and_ground_answer


def test_verify_and_ground_keeps_supported_numeric_fact():
    query = "сколько жмет анти тренер"
    answer = "Анти-тренер жмет 180 кг. Он лучший в мире."
    chunks = [
        {"text": "В выпуске сказано: анти тренер жмёт 180 кг и делает это уверенно."},
        {"text": "Позитивная музыка 3, 4, 5, 6, 7."},
    ]
    out = _verify_and_ground_answer(query, answer, chunks)
    assert "180 кг" in out
    assert "лучший в мире" not in out


def test_verify_and_ground_drops_noise_numeric_line():
    query = "сколько жмет анти тренер"
    answer = "По базе знаний: ПОЗИТИВНАЯ МУЗЫКА 3, 4, 5, 6."
    chunks = [
        {"text": "Позитивная музыка 3, 4, 5, 6, 7, 8."},
        {"text": "Антитренер сегодня сделал жим 180 кг."},
    ]
    out = _verify_and_ground_answer(query, answer, chunks)
    assert "ПОЗИТИВНАЯ МУЗЫКА" not in out
