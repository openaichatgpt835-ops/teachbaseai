cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
import redis
from rq.registry import FailedJobRegistry
from rq import Queue

r = redis.Redis(host='redis', port=6379)
fr = FailedJobRegistry('ingest', connection=r)
q = Queue('ingest', connection=r)
cnt = fr.count
for jid in fr.get_job_ids():
    fr.remove(jid, delete_job=True)
print('cleared_ingest_failed=', cnt)
print('ingest_failed_now=', fr.count)
print('ingest_started_now=', q.started_job_registry.count)
print('ingest_queued_now=', q.count)
PY
