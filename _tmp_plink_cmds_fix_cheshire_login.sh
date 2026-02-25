cd /opt/teachbaseai
set -e
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
from datetime import datetime
from sqlalchemy import select
from apps.backend.database import get_session_factory
from apps.backend.models.account import AppUserWebCredential, AccountMembership
from apps.backend.models.portal import Portal
from apps.backend.models.web_user import WebUser

email='cheshirskithecat@mail.ru'
SessionLocal=get_session_factory()
db=SessionLocal()
try:
    cred=db.execute(select(AppUserWebCredential).where(AppUserWebCredential.email==email)).scalar_one_or_none()
    if not cred:
        print('NO_CREDENTIAL')
        raise SystemExit(0)
    wu=db.execute(select(WebUser).where(WebUser.email==email)).scalar_one_or_none()
    if wu:
        print('ALREADY_EXISTS', wu.id)
        raise SystemExit(0)
    mem=db.execute(select(AccountMembership).where(AccountMembership.user_id==cred.user_id, AccountMembership.status.in_(['active','invited'])).order_by(AccountMembership.id.asc())).scalar_one_or_none()
    if not mem:
        print('NO_MEMBERSHIP')
        raise SystemExit(0)
    portal=db.execute(select(Portal).where(Portal.account_id==mem.account_id).order_by(Portal.id.asc())).scalar_one_or_none()
    if not portal:
        print('NO_PORTAL')
        raise SystemExit(0)
    now=datetime.utcnow()
    wu=WebUser(email=email,password_hash=cred.password_hash,portal_id=portal.id,email_verified_at=now,created_at=now,updated_at=now)
    db.add(wu)
    db.commit()
    print('CREATED', wu.id, portal.id)
finally:
    db.close()
PY
