docker exec -i teachbaseai-backend-1 sh -lc 'cat > /tmp/enqueue_kb_jobs.py <<"PY"
from apps.backend.database import get_session_factory
from apps.backend.models.kb import KBJob
from sqlalchemy import select
from redis import Redis
from rq import Queue
from apps.backend.config import get_settings

s = get_settings()
r = Redis(host=s.redis_host, port=s.redis_port)
q = Queue("default", connection=r)

with get_session_factory()() as db:
    jobs = db.execute(select(KBJob).where(KBJob.status=="queued")).scalars().all()
    for j in jobs:
        q.enqueue("apps.worker.jobs.process_kb_job", j.id)
    print("enqueued", len(jobs))
PY
python /tmp/enqueue_kb_jobs.py'
