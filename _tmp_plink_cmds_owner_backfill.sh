cd /opt/teachbaseai
set -e
docker compose -f docker-compose.prod.yml exec -T backend python -m apps.backend.scripts.rbac_owner_backfill
docker compose -f docker-compose.prod.yml exec -T backend python -m apps.backend.scripts.rbac_owner_backfill --commit
