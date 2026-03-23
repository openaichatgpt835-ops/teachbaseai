cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T worker-ingest python - <<'PY'
import tempfile, os
from apps.backend.services.kb_ingest import _extract_audio_to_wav, _diarize_track
src='/app/storage/kb/2/СКОЛЬКО ПОДНИМЕТ СПАРТАК.mp3'
with tempfile.TemporaryDirectory() as td:
    wav=os.path.join(td,'a.wav')
    _extract_audio_to_wav(src,wav)
    spans=_diarize_track(wav)
    s=set(sp for _,_,sp in spans)
    print('spans', len(spans))
    print('unique', len(s), sorted(list(s))[:10])
PY