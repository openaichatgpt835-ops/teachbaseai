cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T worker-ingest python - <<'PY'
import os
from apps.backend.services.kb_ingest import _get_diarization_pipeline
print('enabled', (os.getenv('ENABLE_SPEAKER_DIARIZATION') or ''))
print('token_present', bool((os.getenv('PYANNOTE_TOKEN') or os.getenv('HUGGINGFACE_TOKEN') or '').strip()))
pipe=_get_diarization_pipeline()
print('pipe_none', pipe is None)
print('pipe_type', type(pipe).__name__ if pipe is not None else None)
PY