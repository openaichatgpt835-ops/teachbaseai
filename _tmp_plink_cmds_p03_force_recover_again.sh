docker exec teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "update kb_jobs set updated_at=now()-interval '20 minutes' where id=71 and status='processing';"
docker exec teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "update kb_files set updated_at=now()-interval '20 minutes' where id=41 and status='processing';"
docker exec -i teachbaseai-backend-1 python - <<'PY'
from apps.backend.services.kb_job_watchdog import recover_stuck_kb_jobs_once
print(recover_stuck_kb_jobs_once(stale_seconds=60, batch_limit=200))
PY
docker exec teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, status, error_message, updated_at from kb_jobs where (payload_json->>'file_id')='41' order by id desc limit 6;"
