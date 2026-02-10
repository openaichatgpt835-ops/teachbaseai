"""Сохранение/чтение токенов порталов (с шифрованием)."""
from datetime import datetime, timedelta
from typing import Optional
import hashlib
import time

from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.backend.config import get_settings
from apps.backend.models.portal import PortalToken, Portal
from apps.backend.services.token_crypto import encrypt_token, decrypt_token, mask_token
from apps.backend.services.bitrix_logging import log_outbound_oauth_refresh
from apps.backend.clients import bitrix as bitrix_client


class BitrixAuthError(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


def save_tokens(
    db: Session,
    portal_id: int,
    access_token: str,
    refresh_token: str,
    expires_in: int = 3600,
) -> PortalToken:
    s = get_settings()
    enc = s.token_encryption_key if s.token_encryption_key else s.secret_key
    at_enc = encrypt_token(access_token, enc) if access_token else None
    rt_enc = encrypt_token(refresh_token, enc) if refresh_token else None
    expires = datetime.utcnow() + timedelta(seconds=expires_in)
    row = db.query(PortalToken).filter(PortalToken.portal_id == portal_id).first()
    if row:
        row.access_token = at_enc
        if rt_enc is not None:
            row.refresh_token = rt_enc
        row.expires_at = expires
    else:
        row = PortalToken(
            portal_id=portal_id,
            access_token=at_enc,
            refresh_token=rt_enc,
            expires_at=expires,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_access_token(db: Session, portal_id: int) -> Optional[str]:
    row = db.query(PortalToken).filter(PortalToken.portal_id == portal_id).first()
    if not row or not row.access_token:
        return None
    s = get_settings()
    enc = s.token_encryption_key if s.token_encryption_key else s.secret_key
    return decrypt_token(row.access_token, enc)


def get_refresh_token(db: Session, portal_id: int) -> Optional[str]:
    row = db.query(PortalToken).filter(PortalToken.portal_id == portal_id).first()
    if not row or not row.refresh_token:
        return None
    s = get_settings()
    enc = s.token_encryption_key if s.token_encryption_key else s.secret_key
    return decrypt_token(row.refresh_token, enc)


def get_token_mask(db: Session, portal_id: int) -> str:
    row = db.query(PortalToken).filter(PortalToken.portal_id == portal_id).first()
    if not row or not row.access_token:
        return "—"
    s = get_settings()
    enc = s.token_encryption_key if s.token_encryption_key else s.secret_key
    plain = decrypt_token(row.access_token, enc)
    return mask_token(plain)


def _token_md5(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    return hashlib.md5(token.encode()).hexdigest()


def _get_enc_key() -> str:
    s = get_settings()
    return s.token_encryption_key if s.token_encryption_key else s.secret_key


def _load_portal(db: Session, portal_id: int) -> Portal | None:
    return db.query(Portal).filter(Portal.id == portal_id).first()


def _lock_portal_tokens_row(db: Session, portal_id: int) -> PortalToken | None:
    stmt = select(PortalToken).where(PortalToken.portal_id == portal_id).with_for_update()
    return db.execute(stmt).scalar_one_or_none()


def get_client_credentials(db: Session, portal_id: int) -> tuple[str, str, str]:
    portal = _load_portal(db, portal_id)
    if not portal:
        raise BitrixAuthError("portal_not_found", "Portal not found")
    enc = _get_enc_key()
    client_id = (portal.local_client_id or "").strip()
    client_secret = decrypt_token(portal.local_client_secret_encrypted or "", enc) or ""
    install_type = (portal.install_type or "local").strip().lower()
    if client_id and client_secret:
        return client_id, client_secret, "local"
    if install_type == "local":
        raise BitrixAuthError("missing_client_credentials", "Client credentials missing")
    s = get_settings()
    if s.bitrix_client_id and s.bitrix_client_secret:
        return s.bitrix_client_id, s.bitrix_client_secret, "env"
    raise BitrixAuthError("missing_client_credentials", "Client credentials missing")


def refresh_portal_tokens(
    db: Session,
    portal_id: int,
    trace_id: str | None = None,
) -> dict:
    """Refresh OAuth tokens via Bitrix refresh_token. No secrets in logs."""
    portal = _load_portal(db, portal_id)
    if not portal:
        raise BitrixAuthError("portal_not_found", "Portal not found")
    domain = (portal.domain or "").strip()
    if not domain:
        raise BitrixAuthError("missing_domain", "Portal domain missing")
    domain_full = f"https://{domain}" if not domain.startswith("http") else domain

    # Lock tokens row to avoid concurrent refresh
    row = _lock_portal_tokens_row(db, portal_id)
    if not row:
        raise BitrixAuthError("missing_auth", "No tokens row")

    enc = _get_enc_key()
    refresh_plain = decrypt_token(row.refresh_token, enc) if row.refresh_token else None
    if not refresh_plain:
        raise BitrixAuthError("missing_refresh_token", "Refresh token missing")

    client_id, client_secret, creds_source = get_client_credentials(db, portal_id)

    t0 = time.perf_counter()
    data, status_code, err_desc = bitrix_client.refresh_token(domain_full, refresh_plain, client_id, client_secret)
    latency_ms = int((time.perf_counter() - t0) * 1000)

    if not data or not isinstance(data, dict) or not data.get("access_token"):
        log_outbound_oauth_refresh(
            db, trace_id or "", portal_id,
            status_code=status_code or 0,
            latency_ms=latency_ms,
            error_code="bitrix_refresh_failed",
            error_description_safe=(err_desc or "no_response")[:200],
            access_len=None,
            refresh_len=None,
            access_md5=None,
            refresh_md5=None,
            credentials_source=creds_source,
            tokens_updated=False,
        )
        raise BitrixAuthError("bitrix_refresh_failed", err_desc or "refresh failed")

    access_new = str(data.get("access_token") or "")
    refresh_new = str(data.get("refresh_token") or "") or refresh_plain
    expires_in = int(data.get("expires_in") or 3600)

    save_tokens(db, portal_id, access_new, refresh_new, expires_in)

    log_outbound_oauth_refresh(
        db, trace_id or "", portal_id,
        status_code=status_code or 200,
        latency_ms=latency_ms,
        error_code=None,
        error_description_safe=None,
        access_len=len(access_new),
        refresh_len=len(refresh_new),
        access_md5=_token_md5(access_new),
        refresh_md5=_token_md5(refresh_new),
        credentials_source=creds_source,
        tokens_updated=True,
    )
    return {
        "access_token": access_new,
        "refresh_token": refresh_new,
        "expires_in": expires_in,
    }


def ensure_fresh_access_token(
    db: Session,
    portal_id: int,
    now: datetime | None = None,
    skew_seconds: int = 120,
    trace_id: str | None = None,
    force: bool = False,
) -> str:
    """Return access token; refresh if expired/near expiry or force=True."""
    row = db.query(PortalToken).filter(PortalToken.portal_id == portal_id).first()
    if not row or not row.access_token:
        raise BitrixAuthError("missing_access_token", "Access token missing")
    enc = _get_enc_key()
    access_plain = decrypt_token(row.access_token, enc)
    if not access_plain:
        raise BitrixAuthError("access_token_decrypt_failed", "Access token decrypt failed")

    if force:
        refreshed = refresh_portal_tokens(db, portal_id, trace_id=trace_id)
        return refreshed["access_token"]

    if row.expires_at:
        now_dt = now or datetime.utcnow()
        if row.expires_at <= (now_dt + timedelta(seconds=skew_seconds)):
            refreshed = refresh_portal_tokens(db, portal_id, trace_id=trace_id)
            return refreshed["access_token"]
    return access_plain


def get_valid_access_token(
    db: Session,
    portal_id: int,
    now: datetime | None = None,
    skew_seconds: int = 120,
    trace_id: str | None = None,
) -> str:
    """Backward-compatible wrapper."""
    return ensure_fresh_access_token(
        db, portal_id, now=now, skew_seconds=skew_seconds, trace_id=trace_id, force=False
    )
