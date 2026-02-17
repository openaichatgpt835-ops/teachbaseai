cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python -c 'from apps.backend.services.kb_job_watchdog import run_kb_watchdog_cycle; print(run_kb_watchdog_cycle())'
