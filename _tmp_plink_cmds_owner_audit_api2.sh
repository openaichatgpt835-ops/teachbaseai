cd /opt/teachbaseai
set -e
TOKEN=$(docker compose -f docker-compose.prod.yml exec -T backend sh -lc "python - <<'PY'
import json
from fastapi.testclient import TestClient
from apps.backend.main import app
c=TestClient(app)
r=c.post('/v1/admin/auth/refresh')
print(r.status_code)
print(r.text)
PY")
echo "$TOKEN"
