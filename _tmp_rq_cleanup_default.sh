cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
import redis
from rq import Queue
from rq.registry import FailedJobRegistry

r = redis.Redis(host='redis', port=6379)
q_def = Queue('default', connection=r)
q_ing = Queue('ingest', connection=r)

migrated = 0
for jid in list(q_def.job_ids):
    j = q_def.fetch_job(jid)
    if not j:
        continue
    if j.func_name == 'apps.worker.jobs.process_kb_job' and j.args:
        job_id = int(j.args[0])
        q_ing.enqueue('apps.worker.jobs.process_kb_job', job_id, job_id=f'kbjob:{job_id}', job_timeout=3600)
        migrated += 1
    q_def.remove(jid)

fr_def = FailedJobRegistry('default', connection=r)
def_failed = fr_def.count
for jid in fr_def.get_job_ids():
    fr_def.remove(jid, delete_job=True)

print('migrated_from_default_to_ingest=', migrated)
print('cleared_default_failed=', def_failed)
print('default_queued_now=', q_def.count)
print('default_failed_now=', fr_def.count)
PY
