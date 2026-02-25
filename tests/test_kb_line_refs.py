from apps.backend.services.kb_rag import _build_line_refs, _dedup_used_chunks


def test_line_refs_can_include_more_than_three_sources_when_relevant():
    answer = "Анти-тренер жмет 180 кг."
    sources = []
    for i in range(7):
        sources.append(
            {
                "text": "В выпуске сказано, что анти-тренер жмет 180 кг и делает это уверенно.",
                "filename": f"src_{i}.mp3",
                "score": 0.42,
            }
        )

    refs = _build_line_refs(answer, sources, query="сколько жмет анти тренер")

    assert "0" in refs
    assert len(refs["0"]) == 7


def test_dedup_used_chunks_removes_duplicates_by_identity():
    chunks = [
        {"chunk_id": 10, "file_id": 1, "chunk_index": 5, "text": "a"},
        {"chunk_id": 10, "file_id": 1, "chunk_index": 5, "text": "a duplicate"},
        {"chunk_id": 11, "file_id": 1, "chunk_index": 6, "text": "b"},
    ]

    out = _dedup_used_chunks(chunks)

    assert len(out) == 2
    assert out[0]["chunk_id"] == 10
    assert out[1]["chunk_id"] == 11
