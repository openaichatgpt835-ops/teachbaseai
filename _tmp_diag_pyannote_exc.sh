cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T worker-ingest python - <<'PY'
import os, traceback
from pyannote.audio import Pipeline
token=(os.getenv('PYANNOTE_TOKEN') or os.getenv('HUGGINGFACE_TOKEN') or '').strip()
try:
    p=Pipeline.from_pretrained('pyannote/speaker-diarization-3.1', use_auth_token=token)
    print('ok', type(p))
except Exception as e:
    print('err', type(e).__name__, str(e))
    traceback.print_exc()
PY