docker exec -i teachbaseai-backend-1 python - <<'PY'
from redis import Redis
from rq import Queue
from apps.backend.config import get_settings
s = get_settings()
r = Redis(host=s.redis_host, port=s.redis_port)
q = Queue('default', connection=r)
job = q.enqueue('apps.worker.jobs.process_kb_job', 48, job_timeout=1800)
print('enqueued', job.id)
PY
