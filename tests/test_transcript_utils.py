from apps.backend.services.transcript_utils import merge_transcript_items


def test_merge_adjacent_same_speaker_by_gap():
    items = [
        {"id": 1, "speaker": "Спикер A", "text": "Первая фраза.", "start_ms": 1000, "end_ms": 3000},
        {"id": 2, "speaker": "Спикер A", "text": "Вторая фраза.", "start_ms": 3200, "end_ms": 5000},
        {"id": 3, "speaker": "Спикер B", "text": "Третья фраза.", "start_ms": 5200, "end_ms": 7000},
    ]
    out = merge_transcript_items(items, max_gap_ms=500)
    assert len(out) == 2
    assert out[0]["speaker"] == "Спикер A"
    assert out[0]["text"] == "Первая фраза. Вторая фраза."
    assert out[0]["start_ms"] == 1000
    assert out[0]["end_ms"] == 5000
    assert out[1]["speaker"] == "Спикер B"


def test_do_not_merge_when_gap_too_large():
    items = [
        {"id": 1, "speaker": "Спикер A", "text": "Первая.", "start_ms": 1000, "end_ms": 2000},
        {"id": 2, "speaker": "Спикер A", "text": "Вторая.", "start_ms": 7000, "end_ms": 8000},
    ]
    out = merge_transcript_items(items, max_gap_ms=3000)
    assert len(out) == 2


def test_do_not_merge_non_adjacent_same_speaker():
    items = [
        {"id": 1, "speaker": "Спикер A", "text": "A1", "start_ms": 0, "end_ms": 1000},
        {"id": 2, "speaker": "Спикер B", "text": "B1", "start_ms": 1100, "end_ms": 2000},
        {"id": 3, "speaker": "Спикер A", "text": "A2", "start_ms": 2100, "end_ms": 2800},
    ]
    out = merge_transcript_items(items, max_gap_ms=500)
    assert len(out) == 3


def test_keep_rare_speaker_segments():
    items = [
        {"id": 1, "speaker": "Спикер A", "text": "A1", "start_ms": 0, "end_ms": 1000},
        {"id": 2, "speaker": "Спикер C", "text": "Короткая реплика", "start_ms": 1100, "end_ms": 1300},
        {"id": 3, "speaker": "Спикер A", "text": "A2", "start_ms": 1400, "end_ms": 2000},
    ]
    out = merge_transcript_items(items, max_gap_ms=1000)
    assert len(out) == 3
    assert out[1]["speaker"] == "Спикер C"
