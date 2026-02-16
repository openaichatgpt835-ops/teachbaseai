from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.backend.models.web_user import WebEmailToken, WebUser
from apps.backend.services.email import send_email
from apps.backend.routers.admin_registrations import _get_settings, _get_templates, _resolve_port
from apps.backend.config import get_settings


def create_email_token(db: Session, user_id: int, kind: str = "confirm") -> str:
    token = secrets.token_urlsafe(32)
    rec = WebEmailToken(
        user_id=user_id,
        token=token,
        kind=kind,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=2),
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
) -> tuple[bool, str | None]:
    settings = _get_settings(db)
    templates = _get_templates(db)
    mb = settings.get("registration") or {}
    tpl = templates.get(template_key) or {}
    subject = str(tpl.get("subject") or "Teachbase AI")
    html = str(tpl.get("html") or "")
    text = str(tpl.get("text") or "")
    if confirm_url:
        html = html.replace("{{confirm_url}}", confirm_url)
        text = text.replace("{{confirm_url}}", confirm_url)
    port = _resolve_port(mb.get("smtp_port"), str(mb.get("smtp_secure") or ""))
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


def get_valid_confirm_token(db: Session, token: str) -> WebEmailToken | None:
    rec = db.execute(
        select(WebEmailToken).where(
            WebEmailToken.token == token,
            WebEmailToken.used_at.is_(None),
        )
    ).scalar_one_or_none()
    if not rec:
        return None
    if rec.expires_at and rec.expires_at < datetime.utcnow():
        return None
    return rec
