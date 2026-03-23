cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
import redis
from rq import Queue
from rq.registry import FailedJobRegistry
r = redis.Redis(host='redis', port=6379)
for n in ['ingest','outbox','default']:
 q=Queue(n,connection=r); fr=FailedJobRegistry(n,connection=r)
 print(n,'queued',q.count,'started',q.started_job_registry.count,'failed',fr.count)
PY
