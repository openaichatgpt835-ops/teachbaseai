cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
from apps.backend.database import get_session_factory
from apps.backend.models.web_user import WebUser
from apps.backend.models.admin import AdminUser
from sqlalchemy import select

EMAIL = "lagutinaleks@gmail.com"
Session = get_session_factory()
with Session() as db:
    web = db.execute(select(WebUser).where(WebUser.email == EMAIL)).scalar_one_or_none()
    admin = db.execute(select(AdminUser).where(AdminUser.email == EMAIL)).scalar_one_or_none()
    print("web_user", bool(web))
    print("admin_user", bool(admin))
PY
