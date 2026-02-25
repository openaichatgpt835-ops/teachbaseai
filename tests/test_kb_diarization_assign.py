from apps.backend.services.kb_ingest import _Segment, _assign_speakers_from_spans


def test_assign_speakers_from_spans_overlap():
    segs = [
        _Segment(text="a", start_ms=0, end_ms=1000),
        _Segment(text="b", start_ms=1100, end_ms=2000),
        _Segment(text="c", start_ms=2100, end_ms=3000),
    ]
    spans = [
        (0, 1500, "SPEAKER_0"),
        (1500, 4000, "SPEAKER_1"),
    ]
    out = _assign_speakers_from_spans(segs, spans)
    assert out[0].speaker == "Спикер A"
    assert out[1].speaker == "Спикер B"
    assert out[2].speaker == "Спикер B"


def test_assign_speakers_without_spans_defaults_to_a():
    segs = [_Segment(text="x", start_ms=0, end_ms=1000)]
    out = _assign_speakers_from_spans(segs, [])
    assert out[0].speaker == "Спикер A"
