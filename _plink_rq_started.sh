cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python -c 'from redis import Redis; from rq import Queue; from rq.job import Job; from apps.backend.config import get_settings; s=get_settings(); r=Redis(host=s.redis_host, port=s.redis_port); q=Queue("default", connection=r); ids=q.started_job_registry.get_job_ids(); print("started_ids", ids); 
for jid in ids:
 j=Job.fetch(jid, connection=r); print({"rq_job_id": j.id, "func": j.func_name, "args": j.args, "enqueued_at": (j.enqueued_at.isoformat() if j.enqueued_at else None), "started_at": (j.started_at.isoformat() if j.started_at else None), "timeout": j.timeout, "meta": j.meta})'
