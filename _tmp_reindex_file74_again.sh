cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
from datetime import datetime, UTC
from redis import Redis
from rq import Queue
from sqlalchemy import select, delete
from apps.backend.config import get_settings
from apps.backend.database import get_session_factory
from apps.backend.models.kb import KBFile, KBJob, KBChunk, KBEmbedding

FILE_ID = 74
settings = get_settings()
r = Redis(host=settings.redis_host, port=settings.redis_port)
q = Queue('ingest', connection=r)

with get_session_factory()() as db:
    f = db.get(KBFile, FILE_ID)
    db.execute(delete(KBEmbedding).where(KBEmbedding.chunk_id.in_(select(KBChunk.id).where(KBChunk.file_id==FILE_ID))))
    db.execute(delete(KBChunk).where(KBChunk.file_id==FILE_ID))
    f.status='uploaded'; f.error_message=None; f.transcript_status='uploaded'; f.transcript_error=None
    db.add(f)
    j=KBJob(portal_id=f.portal_id,job_type='ingest',status='queued',payload_json={'file_id': f.id},trace_id=None,created_at=datetime.now(UTC),updated_at=datetime.now(UTC))
    db.add(j); db.commit()
    q.enqueue('apps.worker.jobs.process_kb_job', j.id, job_id=f'kbjob:{j.id}', result_ttl=500)
    print('enqueued_job', j.id)
PY