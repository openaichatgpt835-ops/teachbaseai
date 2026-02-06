cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
from apps.backend.database import get_session_factory
from apps.backend.models.outbox import Outbox
from sqlalchemy import select
from redis import Redis
from rq import Queue
from apps.backend.config import get_settings
s = get_settings()
factory = get_session_factory()
with factory() as db:
    ids = [o.id for o in db.execute(select(Outbox).where(Outbox.status=="created")).scalars().all()]
print("requeue", ids)
r = Redis(host=s.redis_host, port=s.redis_port)
q = Queue("default", connection=r)
for oid in ids:
    q.enqueue("apps.worker.jobs.process_outbox", oid)
PY
