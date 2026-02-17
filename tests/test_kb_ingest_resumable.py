"""Resumable media transcription helpers."""

from pathlib import Path

from apps.backend.services import kb_ingest


def test_transcribe_media_resumable_continues_from_checkpoint(monkeypatch, tmp_path: Path):
    transcript = tmp_path / "sample.transcript.jsonl"
    # Existing checkpoint segment [0..5000]
    kb_ingest._append_transcript_segment_jsonl(
        str(transcript),
        kb_ingest._Segment(text="hello", start_ms=0, end_ms=5000),
    )

    monkeypatch.setattr(kb_ingest, "_media_duration_seconds", lambda _p: 20)

    def fake_window(_path: str, start_sec: int, _duration_sec: int):
        # Return one segment per window with local times.
        return [kb_ingest._Segment(text=f"w{start_sec}", start_ms=0, end_ms=1000)]

    monkeypatch.setattr(kb_ingest, "_transcribe_media_window", fake_window)
    monkeypatch.setattr(kb_ingest, "_MEDIA_CHUNK_SECONDS", 10)
    monkeypatch.setattr(kb_ingest, "_MEDIA_CHUNK_OVERLAP_SECONDS", 2)

    progress = []
    out = kb_ingest._transcribe_media_resumable(
        src_path="dummy.wav",
        transcript_jsonl_path=str(transcript),
        progress_cb=lambda p: progress.append(int(p)),
    )

    # Existing + resumed windows (first overlap window at 3s is skipped as duplicate).
    assert len(out) >= 2
    assert any(seg.text == "w11" for seg in out)
    assert progress and progress[-1] == 100
