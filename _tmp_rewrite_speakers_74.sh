cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T worker-ingest python - <<'PY'
import os, tempfile
from collections import Counter
from apps.backend.services.kb_ingest import (
    _extract_audio_to_wav,
    _diarize_track,
    _read_transcript_segments_jsonl,
    _assign_speakers_from_spans,
    _write_transcript_segments_jsonl,
)

base='/app/storage/kb/2/СКОЛЬКО ПОДНИМЕТ СПАРТАК.mp3'
jsonl=base + '.transcript.jsonl'
segments=_read_transcript_segments_jsonl(jsonl)
print('segments_before', len(segments))
print('speakers_before', Counter((s.speaker or '').strip() or '<empty>' for s in segments))
with tempfile.TemporaryDirectory() as td:
    wav=os.path.join(td,'a.wav')
    _extract_audio_to_wav(base, wav)
    spans=_diarize_track(wav)
print('spans', len(spans), 'unique', len(set(sp for _,_,sp in spans)))
segments2=_assign_speakers_from_spans(segments, spans)
_write_transcript_segments_jsonl(jsonl, segments2)
print('speakers_after', Counter((s.speaker or '').strip() or '<empty>' for s in segments2))
PY