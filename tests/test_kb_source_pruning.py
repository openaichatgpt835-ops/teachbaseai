from apps.backend.services.kb_rag import _prune_sources_by_line_refs, _prune_sources_with_line_ref_remap


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


def test_prune_sources_only_referenced_when_flag_disabled():
    sources = [{"filename": f"f{i}.txt"} for i in range(8)]
    refs = {"0": [5], "1": [2]}
    out = _prune_sources_by_line_refs(sources, refs, max_items=6, include_unreferenced=False)
    assert [s["filename"] for s in out] == ["f5.txt", "f2.txt"]


def test_prune_with_remap_keeps_line_refs_consistent():
    sources = [{"filename": f"f{i}.txt"} for i in range(8)]
    refs = {"0": [5, 2], "1": [2, 7]}
    pruned, remapped = _prune_sources_with_line_ref_remap(
        sources,
        refs,
        max_items=3,
        include_unreferenced=False,
    )
    assert [s["filename"] for s in pruned] == ["f5.txt", "f2.txt", "f7.txt"]
    assert remapped == {"0": [0, 1], "1": [1, 2]}
