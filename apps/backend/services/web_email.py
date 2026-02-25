from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.backend.config import get_settings
from apps.backend.models.app_setting import AppSetting
from apps.backend.models.web_user import WebEmailToken, WebUser
from apps.backend.services.email import send_email

SETTINGS_KEY = "mail_settings"
TEMPLATES_KEY = "mail_templates"


def _mail_settings_defaults() -> dict:
    return {
        "registration": {
            "smtp_host": "",
            "smtp_port": "587",
            "smtp_user": "",
            "smtp_password": "",
            "smtp_secure": "tls",
            "from_email": "",
            "from_name": "",
        }
    }


def _mail_templates_defaults() -> dict:
    return {
        "registration": {
            "subject": "Подтвердите регистрацию в Teachbase AI",
            "html": "",
            "text": "Ссылка подтверждения: {{confirm_url}}",
        },
        "registration_confirmed": {
            "subject": "Регистрация подтверждена",
            "html": "",
            "text": "Регистрация подтверждена.",
        },
        "password_reset": {
            "subject": "Сброс пароля Teachbase AI",
            "html": "",
            "text": "Ссылка для сброса пароля: {{reset_url}}",
        },
    }


def _get_settings_local(db: Session) -> dict:
    row = db.get(AppSetting, SETTINGS_KEY)
    if not row or not isinstance(row.value_json, dict):
        return _mail_settings_defaults()
    data = row.value_json
    base = _mail_settings_defaults()
    reg = data.get("registration") if isinstance(data.get("registration"), dict) else {}
    out = dict(base["registration"])
    for k in out.keys():
        if reg.get(k) is not None:
            out[k] = reg.get(k)
    return {"registration": out}


def _get_templates_local(db: Session) -> dict:
    row = db.get(AppSetting, TEMPLATES_KEY)
    if not row or not isinstance(row.value_json, dict):
        return _mail_templates_defaults()
    data = row.value_json
    base = _mail_templates_defaults()
    out = dict(base)
    for key in ("registration", "registration_confirmed", "password_reset", "account_invite"):
        val = data.get(key)
        if isinstance(val, dict):
            merged = dict(out.get(key, {}))
            merged.update(val)
            out[key] = merged
    return out


def _resolve_port_local(raw: str | int | None, secure: str) -> int:
    if isinstance(raw, int):
        return raw
    text = str(raw or "").strip()
    parts = [p for p in text.replace(",", ":").split(":") if p.strip().isdigit()]
    ports = [int(p) for p in parts] if parts else []
    if secure == "ssl" and 465 in ports:
        return 465
    if secure == "tls" and 587 in ports:
        return 587
    if 25 in ports:
        return 25
    if ports:
        return ports[0]
    return 465 if secure == "ssl" else (587 if secure == "tls" else 25)


def create_email_token(
    db: Session,
    user_id: int,
    kind: str = "confirm",
    *,
    expires_in: timedelta | None = None,
) -> str:
    token = secrets.token_urlsafe(32)
    rec = WebEmailToken(
        user_id=user_id,
        token=token,
        kind=kind,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + (expires_in or timedelta(days=2)),
    )
    db.add(rec)
    db.commit()
    return token


def _send_template_email(
    db: Session,
    *,
    to_email: str,
    template_key: str,
    confirm_url: str | None = None,
    placeholders: dict[str, str] | None = None,
) -> tuple[bool, str | None]:
    settings = _get_settings_local(db)
    templates = _get_templates_local(db)
    mb = settings.get("registration") or {}
    tpl = templates.get(template_key) or {}
    subject = str(tpl.get("subject") or "Teachbase AI")
    html = str(tpl.get("html") or "")
    text = str(tpl.get("text") or "")
    if confirm_url:
        html = html.replace("{{confirm_url}}", confirm_url)
        text = text.replace("{{confirm_url}}", confirm_url)
    for key, value in (placeholders or {}).items():
        html = html.replace(f"{{{{{key}}}}}", value)
        text = text.replace(f"{{{{{key}}}}}", value)
    port = _resolve_port_local(mb.get("smtp_port"), str(mb.get("smtp_secure") or ""))
    return send_email(
        host=str(mb.get("smtp_host") or ""),
        port=port,
        username=str(mb.get("smtp_user") or ""),
        password=str(mb.get("smtp_password") or ""),
        secure=str(mb.get("smtp_secure") or "tls"),
        from_email=str(mb.get("from_email") or ""),
        from_name=str(mb.get("from_name") or ""),
        to_email=to_email,
        subject=subject,
        html=html,
        text=text,
    )


def send_registration_email(db: Session, user: WebUser, token: str) -> tuple[bool, str | None]:
    s = get_settings()
    base = (s.public_base_url or "https://necrogame.ru").rstrip("/")
    confirm_url = f"{base}/confirm?token={token}"
    return _send_template_email(db, to_email=user.email, template_key="registration", confirm_url=confirm_url)


def send_registration_confirmed_email(db: Session, user: WebUser) -> tuple[bool, str | None]:
    return _send_template_email(db, to_email=user.email, template_key="registration_confirmed")


def build_password_reset_url(token: str) -> str:
    s = get_settings()
    base = (s.public_base_url or "https://necrogame.ru").rstrip("/")
    return f"{base}/password/reset?token={token}"


def send_password_reset_email(db: Session, user: WebUser, token: str) -> tuple[bool, str | None]:
    reset_url = build_password_reset_url(token)
    return _send_template_email(
        db,
        to_email=user.email,
        template_key="password_reset",
        placeholders={"reset_url": reset_url},
    )


def build_invite_accept_url(token: str) -> str:
    s = get_settings()
    base = (s.public_base_url or "https://necrogame.ru").rstrip("/")
    return f"{base}/invite/accept?token={token}"


def send_account_invite_email(
    db: Session,
    *,
    to_email: str,
    token: str,
    account_name: str | None = None,
) -> tuple[bool, str | None]:
    accept_url = build_invite_accept_url(token)
    templates = _get_templates_local(db)
    tpl = templates.get("account_invite") if isinstance(templates, dict) else None
    if isinstance(tpl, dict):
        subject = str(tpl.get("subject") or "Приглашение в Teachbase AI")
        html = str(tpl.get("html") or "")
        text = str(tpl.get("text") or "")
    else:
        aname = (account_name or "рабочий аккаунт").strip()
        subject = f"Приглашение в {aname}"
        html = (
            "<div style=\"font-family: 'Segoe UI', Arial, sans-serif; background:#f6f8fc; padding:24px; color:#0f172a;\">"
            "<div style=\"max-width:640px;margin:0 auto;background:#fff;border-radius:18px;padding:28px;border:1px solid #e2e8f0;\">"
            f"<h1 style=\"margin:0 0 12px 0;font-size:22px;\">Приглашение в {aname}</h1>"
            "<p style=\"margin:0 0 12px 0;\">Вас пригласили в аккаунт Teachbase AI. "
            "Нажмите кнопку ниже, чтобы принять приглашение и создать доступ.</p>"
            f"<a href=\"{accept_url}\" style=\"display:inline-block;background:#2563eb;color:#fff;text-decoration:none;padding:12px 18px;border-radius:10px;font-weight:600;\">"
            "Принять приглашение</a>"
            f"<p style=\"margin:16px 0 0 0;font-size:13px;color:#475569;\">Если кнопка не работает, откройте ссылку: {accept_url}</p>"
            "</div></div>"
        )
        text = (
            f"Вас пригласили в {aname}.\n"
            f"Принять приглашение: {accept_url}\n"
            "Если вы не ожидали это письмо, просто игнорируйте его."
        )

    html = html.replace("{{accept_url}}", accept_url).replace("{{account_name}}", account_name or "Teachbase AI")
    text = text.replace("{{accept_url}}", accept_url).replace("{{account_name}}", account_name or "Teachbase AI")

    settings = _get_settings_local(db)
    mb = settings.get("registration") or {}
    port = _resolve_port_local(mb.get("smtp_port"), str(mb.get("smtp_secure") or ""))
    return send_email(
        host=str(mb.get("smtp_host") or ""),
        port=port,
        username=str(mb.get("smtp_user") or ""),
        password=str(mb.get("smtp_password") or ""),
        secure=str(mb.get("smtp_secure") or "tls"),
        from_email=str(mb.get("from_email") or ""),
        from_name=str(mb.get("from_name") or ""),
        to_email=to_email,
        subject=subject,
        html=html,
        text=text,
    )


def get_valid_confirm_token(db: Session, token: str) -> WebEmailToken | None:
    return get_valid_email_token(db, token, kind="confirm")


def get_valid_email_token(db: Session, token: str, *, kind: str | None = None) -> WebEmailToken | None:
    rec = db.execute(
        select(WebEmailToken).where(
            WebEmailToken.token == token,
            WebEmailToken.used_at.is_(None),
        )
    ).scalar_one_or_none()
    if not rec:
        return None
    if kind and (rec.kind or "") != kind:
        return None
    if rec.expires_at and rec.expires_at < datetime.utcnow():
        return None
    return rec
