docker exec -i teachbaseai-backend-1 python - <<'PY'
from apps.backend.database import get_session_factory
from apps.backend.models.kb import KBFile, KBJob
from sqlalchemy import select
from redis import Redis
from rq import Queue
from apps.backend.config import get_settings

s = get_settings()
r = Redis(host=s.redis_host, port=s.redis_port)
q = Queue("default", connection=r)

factory = get_session_factory()
with factory() as db:
    files = db.execute(select(KBFile).where(KBFile.status.in_(["uploaded","error"])) ).scalars().all()
    queued = 0
    for f in files:
        f.status = "queued"
        job = KBJob(portal_id=f.portal_id, job_type="ingest", status="queued", payload_json={"file_id": f.id})
        db.add(job)
        db.flush()
        q.enqueue("apps.worker.jobs.process_kb_job", job.id)
        queued += 1
    db.commit()
print("queued", queued)
PY
