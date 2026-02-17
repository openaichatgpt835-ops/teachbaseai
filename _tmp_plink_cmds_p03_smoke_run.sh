# 1) Restart worker during active ingest processing (simulation of deploy interruption)
docker restart teachbaseai-worker-1

# 2) Backdate any processing ingest jobs/files to force stale condition for quick smoke

docker exec teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "update kb_jobs set updated_at=now() - interval '20 minutes' where job_type='ingest' and status='processing';"
docker exec teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "update kb_files set updated_at=now() - interval '20 minutes' where status='processing';"

# 3) Run watchdog recovery once with small stale threshold

docker exec -i teachbaseai-backend-1 python - <<'PY'
from apps.backend.services.kb_job_watchdog import recover_stuck_kb_jobs_once
print(recover_stuck_kb_jobs_once(stale_seconds=60, batch_limit=200))
PY

# 4) Show resulting statuses

docker exec teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, portal_id, filename, status, error_message, updated_at from kb_files where id=41;"
docker exec teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, job_type, status, payload_json, error_message, updated_at from kb_jobs where (payload_json->>'file_id')='41' order by id desc limit 8;"
docker exec teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select count(*) as processing_files from kb_files where status='processing';"
docker exec teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select count(*) as processing_jobs from kb_jobs where status='processing';"
