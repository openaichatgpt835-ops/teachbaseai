cd /opt/teachbaseai

docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
from apps.backend.config import get_settings
s = get_settings()
print('postgres_host', s.postgres_host)
print('postgres_db', s.postgres_db)
print('postgres_user', s.postgres_user)
print('postgres_port', s.postgres_port)
PY
