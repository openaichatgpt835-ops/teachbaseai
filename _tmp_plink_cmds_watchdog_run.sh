docker exec -i teachbaseai-backend-1 python - <<'PY'
from apps.backend.services.kb_job_watchdog import run_kb_watchdog_cycle
print(run_kb_watchdog_cycle())
PY
