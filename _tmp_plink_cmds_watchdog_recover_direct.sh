docker exec -i teachbaseai-backend-1 python - <<'PY'
from apps.backend.services.kb_job_watchdog import recover_stuck_kb_jobs_once
print(recover_stuck_kb_jobs_once(stale_seconds=60, batch_limit=200))
PY
