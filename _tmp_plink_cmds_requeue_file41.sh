docker exec -i teachbaseai-backend-1 python - <<'PY'
from sqlalchemy import select
from redis import Redis
from rq import Queue
from apps.backend.config import get_settings
from apps.backend.database import get_session_factory
from apps.backend.models.kb import KBFile, KBJob

TARGET_FILE_ID = 41
s = get_settings()
r = Redis(host=s.redis_host, port=s.redis_port)
q = Queue("default", connection=r)

factory = get_session_factory()
with factory() as db:
    f = db.execute(select(KBFile).where(KBFile.id == TARGET_FILE_ID)).scalar_one_or_none()
    if not f:
        print("file_not_found")
    else:
        db.execute(
            KBJob.__table__.update()
            .where((KBJob.payload_json["file_id"].astext == str(TARGET_FILE_ID)) & (KBJob.status.in_(["queued", "processing"])))
            .values(status="failed", error_message="auto_requeued_after_stuck_processing")
        )
        f.status = "queued"
        f.error_message = None
        job = KBJob(portal_id=f.portal_id, job_type="ingest", status="queued", payload_json={"file_id": f.id})
        db.add(job)
        db.flush()
        q.enqueue("apps.worker.jobs.process_kb_job", job.id)
        db.commit()
        print("requeued_job_id", job.id)
PY
