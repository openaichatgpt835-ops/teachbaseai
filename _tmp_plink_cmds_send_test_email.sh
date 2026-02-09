cd /opt/teachbaseai

docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
from apps.backend.database import get_session_factory
from apps.backend.models.app_setting import AppSetting
from apps.backend.services.email import send_email

Session = get_session_factory()
with Session() as db:
    settings = db.get(AppSetting, 'mail_settings')
    templates = db.get(AppSetting, 'mail_templates')
    if not settings:
        print('NO_SETTINGS')
        raise SystemExit(1)
    mb = (settings.value_json or {}).get('registration') or {}
    tpl = ((templates.value_json or {}) if templates else {}).get('registration') or {}
    ok, err = send_email(
        host=mb.get('smtp_host') or '',
        port=int(mb.get('smtp_port') or 0),
        username=mb.get('smtp_user') or '',
        password=mb.get('smtp_password') or '',
        secure=str(mb.get('smtp_secure') or 'tls'),
        from_email=mb.get('from_email') or '',
        from_name=mb.get('from_name') or '',
        to_email='lagutinaleks@gmail.com',
        subject=tpl.get('subject') or 'Teachbase AI',
        html=tpl.get('html') or '',
        text=tpl.get('text') or '',
    )
    print('SEND_OK' if ok else f'SEND_ERR {err}')
PY
