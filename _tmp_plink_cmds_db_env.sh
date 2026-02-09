cd /opt/teachbaseai

docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
import os
print('DATABASE_URL', os.environ.get('DATABASE_URL'))
print('DATABASE_HOST', os.environ.get('DATABASE_HOST'))
print('DATABASE_NAME', os.environ.get('DATABASE_NAME'))
PY
