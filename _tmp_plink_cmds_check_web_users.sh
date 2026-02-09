cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
from apps.backend.database import get_session_factory
from apps.backend.models.web_user import WebUser
from sqlalchemy import select, func

Session = get_session_factory()
with Session() as db:
    total = db.execute(select(func.count(WebUser.id))).scalar()
    print("total", total)
    rows = db.execute(select(WebUser.email).order_by(WebUser.created_at.desc()).limit(20)).scalars().all()
    print("last20", rows)
PY
