docker exec -i teachbaseai-backend-1 python - <<'PY'
from apps.backend.database import get_session_factory
from apps.backend.models.kb import KBJob
from sqlalchemy import select
from redis import Redis
from rq import Queue
from apps.backend.config import get_settings

s = get_settings()
r = Redis(host=s.redis_host, port=s.redis_port)
q = Queue("default", connection=r)

factory = get_session_factory()
with factory() as db:
    jobs = db.execute(select(KBJob).where(KBJob.status == "queued")).scalars().all()
    for job in jobs:
        q.enqueue("apps.worker.jobs.process_kb_job", job.id)
print("enqueued", len(jobs))
PY
