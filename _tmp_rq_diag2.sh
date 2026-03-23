cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
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
    for jid in ids:
        j = q.fetch_job(jid)
        if not j:
            continue
        tail = (j.exc_info or '').splitlines()
        tail = tail[-1] if tail else ''
        print('job', j.id, 'func', j.func_name, 'tail', tail[:200])
PY
