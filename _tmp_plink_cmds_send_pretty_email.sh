cd /opt/teachbaseai

docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
from apps.backend.database import get_session_factory
from apps.backend.models.app_setting import AppSetting
from apps.backend.services.email import send_email
from datetime import datetime

Session = get_session_factory()
html = """
<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;">
  <h2 style="color:#0f172a;">??????????? ??????????? ? Teachbase AI</h2>
  <p>??????? ?? ???????????! ????? ???????????? ???????, ??????????? ???? ?????:</p>
  <p style="margin:24px 0;">
    <a href="https://necrogame.ru/verify?token=TEST" style="background:#0ea5e9;color:#fff;text-decoration:none;padding:12px 18px;border-radius:10px;display:inline-block;">??????????? ???????????</a>
  </p>
  <p style="color:#64748b;font-size:12px;">???? ?? ?? ????????????????, ?????? ?????????????? ??? ??????.</p>
</div>
"""
text = "??????????? ???????????: https://necrogame.ru/verify?token=TEST"

with Session() as db:
    row = db.get(AppSetting, 'mail_templates')
    data = row.value_json if row else {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault('registration', {})
    data['registration'] = {
        'subject': '??????????? ??????????? ? Teachbase AI',
        'html': html,
        'text': text,
    }
    if not row:
        row = AppSetting(key='mail_templates', value_json=data)
        db.add(row)
    else:
        row.value_json = data
    db.commit()

    settings = db.get(AppSetting, 'mail_settings')
    if not settings:
        print('NO_SETTINGS')
        raise SystemExit(1)
    mb = (settings.value_json or {}).get('registration') or {}
    ok, err = send_email(
        host=mb.get('smtp_host') or '',
        port=int(str(mb.get('smtp_port') or '0').split(':')[0] or 0),
        username=mb.get('smtp_user') or '',
        password=mb.get('smtp_password') or '',
        secure=str(mb.get('smtp_secure') or 'tls'),
        from_email=mb.get('from_email') or '',
        from_name=mb.get('from_name') or '',
        to_email='lagutinaleks@gmail.com',
        subject=data['registration']['subject'],
        html=html,
        text=text,
    )
    print('SEND_OK' if ok else f'SEND_ERR {err}')
PY
