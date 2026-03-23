cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T worker-ingest python - <<'PY'
from pyannote.audio import Pipeline
import os

token=(os.getenv('PYANNOTE_TOKEN') or os.getenv('HUGGINGFACE_TOKEN') or '').strip()
try:
    p=Pipeline.from_pretrained('pyannote/speaker-diarization-3.1', use_auth_token=token)
    print('pipeline_ok', type(p).__name__)
except Exception as e:
    import traceback
    print('pipeline_err', type(e).__name__, str(e)[:300])
    traceback.print_exc()
PY