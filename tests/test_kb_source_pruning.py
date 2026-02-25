from apps.backend.services.kb_rag import _prune_sources_by_line_refs


def test_prune_sources_prefers_referenced_indexes():
    sources = [{"filename": f"f{i}.txt"} for i in range(10)]
    refs = {"0": [4, 1], "2": [1, 7]}

    out = _prune_sources_by_line_refs(sources, refs, max_items=5)

    assert [s["filename"] for s in out[:3]] == ["f4.txt", "f1.txt", "f7.txt"]
    assert len(out) == 5


def test_prune_sources_without_refs_keeps_top_slice():
    sources = [{"filename": f"f{i}.txt"} for i in range(6)]

    out = _prune_sources_by_line_refs(sources, {}, max_items=3)

    assert [s["filename"] for s in out] == ["f0.txt", "f1.txt", "f2.txt"]
