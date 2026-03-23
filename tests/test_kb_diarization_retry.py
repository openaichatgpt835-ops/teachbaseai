import types

from apps.backend.services import kb_ingest


class _Turn:
    def __init__(self, start, end):
        self.start = start
        self.end = end


class _DiarObj:
    def __init__(self, rows):
        self.rows = rows

    def itertracks(self, yield_label=True):
        for s, e, sp in self.rows:
            yield _Turn(s, e), None, sp


class _FakePipe:
    def __init__(self):
        self.calls = []

    def __call__(self, path, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return _DiarObj([(0.0, 10.0, "SPEAKER_0")])
        return _DiarObj([(0.0, 5.0, "SPEAKER_0"), (5.0, 10.0, "SPEAKER_1")])


def test_diarization_retries_single_speaker_for_long_audio(monkeypatch):
    pipe = _FakePipe()
    monkeypatch.setattr(kb_ingest, "_get_diarization_pipeline", lambda: pipe)
    monkeypatch.setattr(kb_ingest, "_media_duration_seconds", lambda _p: 3600)
    monkeypatch.setenv("DIARIZATION_RETRY_SINGLE_SPEAKER", "1")
    monkeypatch.setenv("DIARIZATION_RETRY_MIN_DURATION_SEC", "600")
    monkeypatch.setenv("DIARIZATION_RETRY_MIN_SPEAKERS", "2")

    spans = kb_ingest._diarize_track("x.wav")
    speakers = {sp for _s, _e, sp in spans}

    assert len(pipe.calls) == 2
    assert speakers == {"SPEAKER_0", "SPEAKER_1"}
    assert pipe.calls[1].get("min_speakers") == 2


def test_diarization_no_retry_for_short_audio(monkeypatch):
    pipe = _FakePipe()
    monkeypatch.setattr(kb_ingest, "_get_diarization_pipeline", lambda: pipe)
    monkeypatch.setattr(kb_ingest, "_media_duration_seconds", lambda _p: 120)
    monkeypatch.setenv("DIARIZATION_RETRY_SINGLE_SPEAKER", "1")
    monkeypatch.setenv("DIARIZATION_RETRY_MIN_DURATION_SEC", "600")

    spans = kb_ingest._diarize_track("x.wav")
    speakers = {sp for _s, _e, sp in spans}

    assert len(pipe.calls) == 1
    assert speakers == {"SPEAKER_0"}
