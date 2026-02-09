cd /opt/teachbaseai

docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
from apps.backend import config
print('db_url', getattr(config, 'DATABASE_URL', None))
print('db_host', getattr(config, 'DATABASE_HOST', None))
print('db_name', getattr(config, 'DATABASE_NAME', None))
print('db_user', getattr(config, 'DATABASE_USER', None))
print('db_port', getattr(config, 'DATABASE_PORT', None))
PY
