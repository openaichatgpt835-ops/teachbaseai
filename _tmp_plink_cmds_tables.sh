cd /opt/teachbaseai

docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
from apps.backend.database import get_session_factory
from sqlalchemy import text

Session = get_session_factory()
with Session() as db:
    rows = db.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"))
    tables = [r[0] for r in rows]
    print('tables', [t for t in tables if 'web' in t or 'user' in t])
    for t in ['web_users','web_user_sessions','admin_users']:
        try:
            count = db.execute(text(f"SELECT count(*) FROM {t}")).scalar()
            print(t, count)
        except Exception as e:
            print(t, 'ERR', e)
PY
