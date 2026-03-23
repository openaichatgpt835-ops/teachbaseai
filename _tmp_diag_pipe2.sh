cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T worker-ingest python - <<'PY'
import os
from apps.backend.services.kb_ingest import _get_diarization_pipeline
pipe=_get_diarization_pipeline()
print('pipe_none', pipe is None)
print('type', type(pipe).__name__ if pipe else None)
PY