cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
from apps.backend.database import get_session_factory
from apps.backend.models.web_user import WebUser
from apps.backend.auth import get_password_hash
from sqlalchemy import select

EMAIL = "lagutinaleks@gmail.com"
NEW_PASS = "Teachbase2026!"

Session = get_session_factory()
with Session() as db:
    user = db.execute(select(WebUser).where(WebUser.email == EMAIL)).scalar_one_or_none()
    if not user:
        print("NOT_FOUND")
    else:
        user.password_hash = get_password_hash(NEW_PASS)
        db.add(user)
        db.commit()
        print("OK")
PY
