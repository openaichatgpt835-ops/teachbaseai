"""Portal telegram settings helpers."""
from __future__ import annotations

import secrets
from typing import Any

from sqlalchemy.orm import Session

from apps.backend.models.portal_telegram_setting import PortalTelegramSetting
from apps.backend.services.token_crypto import encrypt_token, decrypt_token, mask_token
from apps.backend.config import get_settings


def _enc_key() -> str:
    s = get_settings()
    return s.token_encryption_key if s.token_encryption_key else s.secret_key


def _normalize_username(username: str | None) -> str | None:
    if not username:
        return None
    u = username.strip()
    if u.startswith("@"):
        u = u[1:]
    u = u.strip()
    if not u:
        return None
    return u.lower()


def _get_or_create(db: Session, portal_id: int) -> PortalTelegramSetting:
    row = db.get(PortalTelegramSetting, portal_id)
    if not row:
        row = PortalTelegramSetting(portal_id=portal_id)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def get_portal_telegram_settings(db: Session, portal_id: int) -> dict[str, Any]:
    row = db.get(PortalTelegramSetting, portal_id)
    if not row:
        return {
            "staff": {"enabled": False, "has_token": False, "token_masked": ""},
            "client": {"enabled": False, "has_token": False, "token_masked": ""},
        }
    staff_plain = decrypt_token(row.staff_bot_token_enc or "", _enc_key()) if row.staff_bot_token_enc else ""
    client_plain = decrypt_token(row.client_bot_token_enc or "", _enc_key()) if row.client_bot_token_enc else ""
    return {
        "staff": {
            "enabled": bool(row.staff_bot_enabled),
            "has_token": bool(row.staff_bot_token_enc),
            "allow_uploads": bool(row.staff_allow_uploads),
            "token_masked": mask_token(staff_plain) if staff_plain else "",
        },
        "client": {
            "enabled": bool(row.client_bot_enabled),
            "has_token": bool(row.client_bot_token_enc),
            "allow_uploads": bool(row.client_allow_uploads),
            "token_masked": mask_token(client_plain) if client_plain else "",
        },
    }


def get_portal_telegram_token_plain(db: Session, portal_id: int, kind: str) -> str | None:
    row = db.get(PortalTelegramSetting, portal_id)
    if not row:
        return None
    enc = _enc_key()
    if kind == "staff":
        return decrypt_token(row.staff_bot_token_enc or "", enc) if row.staff_bot_token_enc else None
    if kind == "client":
        return decrypt_token(row.client_bot_token_enc or "", enc) if row.client_bot_token_enc else None
    return None


def get_portal_telegram_secret(db: Session, portal_id: int, kind: str) -> str | None:
    row = db.get(PortalTelegramSetting, portal_id)
    if not row:
        return None
    if kind == "staff":
        return row.staff_bot_secret
    if kind == "client":
        return row.client_bot_secret
    return None


def set_portal_telegram_settings(
    db: Session,
    portal_id: int,
    *,
    kind: str,
    bot_token: str | None = None,
    enabled: bool | None = None,
    clear_token: bool = False,
    allow_uploads: bool | None = None,
) -> dict[str, Any]:
    row = _get_or_create(db, portal_id)
    enc_key = _enc_key()
    if kind == "staff":
        if clear_token:
            row.staff_bot_token_enc = None
        if bot_token is not None:
            row.staff_bot_token_enc = encrypt_token(bot_token.strip(), enc_key) if bot_token.strip() else None
        if enabled is not None:
            row.staff_bot_enabled = bool(enabled)
        if allow_uploads is not None:
            row.staff_allow_uploads = bool(allow_uploads)
        if (bot_token or row.staff_bot_token_enc) and not row.staff_bot_secret:
            row.staff_bot_secret = secrets.token_hex(16)
    elif kind == "client":
        if clear_token:
            row.client_bot_token_enc = None
        if bot_token is not None:
            row.client_bot_token_enc = encrypt_token(bot_token.strip(), enc_key) if bot_token.strip() else None
        if enabled is not None:
            row.client_bot_enabled = bool(enabled)
        if allow_uploads is not None:
            row.client_allow_uploads = bool(allow_uploads)
        if (bot_token or row.client_bot_token_enc) and not row.client_bot_secret:
            row.client_bot_secret = secrets.token_hex(16)
    db.add(row)
    db.commit()
    return get_portal_telegram_settings(db, portal_id)


def normalize_telegram_username(username: str | None) -> str | None:
    return _normalize_username(username)
