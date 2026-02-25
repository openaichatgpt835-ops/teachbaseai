cd /opt/teachbaseai
set -e
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
from fastapi.testclient import TestClient
from apps.backend.main import app

c=TestClient(app)
r=c.post('/v1/admin/auth/refresh')
print('refresh', r.status_code)
if r.status_code!=200:
    print(r.text)
    raise SystemExit(1)
tok=r.json().get('access_token')
r2=c.get('/v1/admin/portals/rbac/owners/audit?email=lagutinaleks@gmail.com', headers={'Authorization': f'Bearer {tok}'})
print('audit', r2.status_code)
print(r2.json())
PY
