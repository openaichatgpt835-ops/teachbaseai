cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T worker-ingest python - <<'PY'
from apps.backend.services.kb_ingest import _get_diarization_pipeline
p=_get_diarization_pipeline()
print('pipe_none', p is None)
print('type', type(p).__name__ if p else None)
PY