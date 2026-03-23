from apps.backend.services.kb_rag import _diversify_top_chunks_by_file


def test_diversify_limits_same_file_dominance():
    chunks = [
        {"chunk_id": 1, "file_id": 10},
        {"chunk_id": 2, "file_id": 10},
        {"chunk_id": 3, "file_id": 10},
        {"chunk_id": 4, "file_id": 11},
        {"chunk_id": 5, "file_id": 12},
    ]

    out = _diversify_top_chunks_by_file(chunks, top_k=4, max_per_file=1)
    assert [x["chunk_id"] for x in out] == [1, 4, 5, 2]


def test_diversify_keeps_order_when_already_diverse():
    chunks = [
        {"chunk_id": 1, "file_id": 10},
        {"chunk_id": 2, "file_id": 11},
        {"chunk_id": 3, "file_id": 12},
    ]

    out = _diversify_top_chunks_by_file(chunks, top_k=3, max_per_file=2)
    assert [x["chunk_id"] for x in out] == [1, 2, 3]


def test_diversify_relaxes_limit_for_clear_single_file_head():
    chunks = [
        {"chunk_id": 1, "file_id": 10, "_score": 0.92},
        {"chunk_id": 2, "file_id": 10, "_score": 0.90},
        {"chunk_id": 3, "file_id": 10, "_score": 0.89},
        {"chunk_id": 4, "file_id": 10, "_score": 0.87},
        {"chunk_id": 5, "file_id": 11, "_score": 0.80},
        {"chunk_id": 6, "file_id": 12, "_score": 0.78},
    ]

    out = _diversify_top_chunks_by_file(chunks, top_k=4, max_per_file=2)
    assert [x["chunk_id"] for x in out] == [1, 2, 3, 4]


def test_diversify_stays_diverse_when_other_files_are_competitive():
    chunks = [
        {"chunk_id": 1, "file_id": 10, "_score": 0.92},
        {"chunk_id": 2, "file_id": 10, "_score": 0.88},
        {"chunk_id": 3, "file_id": 10, "_score": 0.70},
        {"chunk_id": 4, "file_id": 11, "_score": 0.91},
        {"chunk_id": 5, "file_id": 12, "_score": 0.89},
        {"chunk_id": 6, "file_id": 13, "_score": 0.87},
    ]

    out = _diversify_top_chunks_by_file(chunks, top_k=4, max_per_file=2)
    assert [x["chunk_id"] for x in out] == [1, 2, 4, 5]
