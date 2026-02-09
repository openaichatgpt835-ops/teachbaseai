set -e
echo START_FLOWTOKEN
docker ps --format "{{.Names}}" | head -n 5
docker exec teachbaseai-backend-1 python -c "print('HELLO_FROM_PY')"
docker exec -i teachbaseai-backend-1 python - <<'PY'
from apps.backend.database import get_session_factory
from apps.backend.models.portal import Portal
from apps.backend.auth import create_portal_token_with_user

SessionLocal = get_session_factory()
s = SessionLocal()
portal = s.query(Portal).filter(Portal.domain == "b24-s57ni9.bitrix24.ru").first()
if not portal:
    print("NO_PORTAL")
    raise SystemExit(0)
uid = portal.admin_user_id or 0
print("PORTAL_ID", portal.id)
print("ADMIN_UID", uid)
if uid:
    token = create_portal_token_with_user(portal.id, int(uid), expires_minutes=30)
    print("PORTAL_TOKEN", token)
else:
    print("NO_ADMIN_UID")
PY
echo END_FLOWTOKEN
