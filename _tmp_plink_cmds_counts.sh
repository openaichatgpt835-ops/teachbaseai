cd /opt/teachbaseai

docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
from apps.backend.database import get_session_factory
from sqlalchemy import select, func
from apps.backend.models.web_user import WebUser
from apps.backend.models.portal import Portal
from apps.backend.models.portal_link_request import PortalLinkRequest
from apps.backend.models.portal_telegram_setting import PortalTelegramSetting

Session = get_session_factory()
with Session() as db:
    def count(model):
        return db.execute(select(func.count(model.id))).scalar()
    print('web_users', count(WebUser))
    print('portals', count(Portal))
    print('portal_link_requests', count(PortalLinkRequest))
    print('portal_telegram_settings', count(PortalTelegramSetting))
PY
