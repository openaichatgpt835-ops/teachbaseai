cd /opt/teachbaseai
cat > /tmp/check_rq.py <<'PY'
import os
import redis
from rq import Queue
from rq.registry import FailedJobRegistry

r = redis.Redis(host='redis', port=6379)
for name in ['ingest','outbox','default']:
    q = Queue(name, connection=r)
    fr = FailedJobRegistry(name, connection=r)
    print(f'=== {name} ===')
    print('queued', q.count, 'failed', fr.count, 'started', q.started_job_registry.count)
    ids = fr.get_job_ids()[:5]
    if ids:
        jobs = q.fetch_many(ids, connection=r)
        for j in jobs:
            if not j:
                continue
            print('job', j.id, 'func', j.func_name, 'enqueued_at', j.enqueued_at, 'exc', (j.exc_info or '').splitlines()[-1][:180])
PY

docker compose -f docker-compose.prod.yml exec -T backend python /tmp/check_rq.py
rm -f /tmp/check_rq.py
