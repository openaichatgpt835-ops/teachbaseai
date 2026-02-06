"""Bitrix REST calls with auto-refresh and retry on auth invalid."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from apps.backend.clients import bitrix as bitrix_client
from apps.backend.models.portal import Portal
from apps.backend.services.portal_tokens import ensure_fresh_access_token, refresh_portal_tokens, BitrixAuthError


def _domain_full(domain: str) -> str:
    d = (domain or "").strip()
    if not d:
        return ""
    return f"https://{d}" if not d.startswith("http") else d


def rest_call_with_refresh(
    db: Session,
    portal_id: int,
    method: str,
    params: dict[str, Any] | None,
    trace_id: str,
    timeout_sec: int = 30,
) -> tuple[dict | None, str | None, str, int, bool]:
    """Call Bitrix REST with auto-refresh on 401/bitrix_auth_invalid.

    Returns: (result, error_code, error_desc_safe, status_code, refreshed)
    """
    portal = db.query(Portal).filter(Portal.id == portal_id).first()
    if not portal:
        return None, "portal_not_found", "Portal not found", 0, False
    domain_full = _domain_full(portal.domain or "")
    if not domain_full:
        return None, "missing_domain", "Portal domain missing", 0, False

    try:
        access_token = ensure_fresh_access_token(db, portal_id, trace_id=trace_id)
    except BitrixAuthError as e:
        return None, e.code, e.detail, 0, False

    result, err, err_desc, status = bitrix_client.rest_call_result_detailed(
        domain_full, access_token, method, params, timeout_sec=timeout_sec
    )
    if err == bitrix_client.BITRIX_ERR_AUTH_INVALID or status == 401 or "expired" in (err_desc or "").lower():
        try:
            refreshed = refresh_portal_tokens(db, portal_id, trace_id=trace_id)
            access_token = refreshed.get("access_token", "")
        except BitrixAuthError as e:
            return None, "bitrix_refresh_failed", e.detail, status or 401, True
        result, err, err_desc, status = bitrix_client.rest_call_result_detailed(
            domain_full, access_token, method, params, timeout_sec=timeout_sec
        )
        return result, err, err_desc, status, True
    return result, err, err_desc, status, False
