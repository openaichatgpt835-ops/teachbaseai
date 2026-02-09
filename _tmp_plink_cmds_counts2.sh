cd /opt/teachbaseai

docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
from apps.backend.database import get_session_factory
from sqlalchemy import text

Session = get_session_factory()
with Session() as db:
    for t in ['web_users','web_sessions','admin_users']:
        try:
            count = db.execute(text(f"SELECT count(*) FROM {t}")).scalar()
            print(t, count)
        except Exception as e:
            print(t, 'ERR', e)
PY
