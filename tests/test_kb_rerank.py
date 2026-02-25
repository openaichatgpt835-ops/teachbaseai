from apps.backend.services.kb_rag import _rerank_candidates


def test_rerank_prioritizes_filename_focus_term():
    query = "дай сюжет серии фоллаут"
    candidates = [
        {
            "chunk_id": 1,
            "file_id": 10,
            "_score": 0.72,
            "text": "Общая информация про сериалы и персонажей.",
            "filename": "С нашей эволюцией что-то не так.mp3",
            "source_title": "",
            "source_url": "",
            "file_summary": "",
        },
        {
            "chunk_id": 2,
            "file_id": 11,
            "_score": 0.61,
            "text": "В серии герой попадает в убежище и сталкивается с рейдерами.",
            "filename": "Сериал Фоллаут - 1 сезон 6 серия.mp3",
            "source_title": "",
            "source_url": "",
            "file_summary": "",
        },
    ]

    out = _rerank_candidates(query, candidates, top_k=2)

    assert out[0]["chunk_id"] == 2


def test_rerank_penalizes_chunks_without_query_evidence():
    query = "кто такой алексей лагутин"
    candidates = [
        {
            "chunk_id": 101,
            "file_id": 21,
            "_score": 0.77,
            "text": "Позитивная музыка 3 4 5 6",
            "filename": "music.mp3",
            "source_title": "",
            "source_url": "",
            "file_summary": "",
        },
        {
            "chunk_id": 102,
            "file_id": 22,
            "_score": 0.63,
            "text": "Алексей Лагутин — ex-руководитель продаж и внедрений.",
            "filename": "about_company.docx",
            "source_title": "",
            "source_url": "",
            "file_summary": "",
        },
    ]

    out = _rerank_candidates(query, candidates, top_k=2)

    assert out[0]["chunk_id"] == 102
