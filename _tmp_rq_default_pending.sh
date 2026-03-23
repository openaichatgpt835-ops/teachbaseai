cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
import redis
from rq import Queue

r = redis.Redis(host='redis', port=6379)
q = Queue('default', connection=r)
ids = q.job_ids
print('default queued ids:', ids)
for jid in ids:
    j = q.fetch_job(jid)
    if j:
        print('id', j.id, 'func', j.func_name, 'args', j.args)
PY
