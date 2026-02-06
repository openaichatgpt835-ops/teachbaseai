"""Provision welcome chats: бот пишет первым выбранным пользователям (imbot.message.add)."""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.backend.models.event import Event
from apps.backend.models.portal import Portal
from apps.backend.services.portal_tokens import ensure_fresh_access_token, BitrixAuthError
from apps.backend.clients import bitrix as bitrix_client

PROVISION_MAX_WORKERS = 3
PROVISION_TIME_BUDGET_SEC = 10


def _portal_meta(portal: Portal) -> dict[str, Any]:
    if not portal.metadata_json:
        return {}
    try:
        data = json.loads(portal.metadata_json)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def provision_welcome_chats(
    db: Session,
    portal_id: int,
    bitrix_user_ids: list[int],
    trace_id: str,
) -> dict[str, Any]:
    """
    Бот пишет первым каждому user_id (DIALOG_ID=user{id}), создаётся личный чат.
    Возвращает {ok_count, fail_count, results: [{user_id, ok, error_code}]}.
    Welcome-текст берётся из portal.welcome_message.
    """
    portal = db.execute(select(Portal).where(Portal.id == portal_id)).scalar_one_or_none()
    if not portal:
        return {"ok_count": 0, "fail_count": len(bitrix_user_ids), "results": [{"user_id": uid, "ok": False, "error_code": "portal_not_found"} for uid in bitrix_user_ids]}

    meta = _portal_meta(portal)
    bot_id = meta.get("bot_id")
    if not bot_id:
        return {"ok_count": 0, "fail_count": len(bitrix_user_ids), "results": [{"user_id": uid, "ok": False, "error_code": "bot_not_registered"} for uid in bitrix_user_ids]}

    domain_raw = (portal.domain or "").strip()
    if not domain_raw:
        return {"ok_count": 0, "fail_count": len(bitrix_user_ids), "results": [{"user_id": uid, "ok": False, "error_code": "portal_no_domain"} for uid in bitrix_user_ids]}
    domain = f"https://{domain_raw}" if not domain_raw.startswith("http") else domain_raw
    try:
        access_token = ensure_fresh_access_token(db, portal_id, trace_id=trace_id)
    except BitrixAuthError as e:
        return {"ok_count": 0, "fail_count": len(bitrix_user_ids), "results": [{"user_id": uid, "ok": False, "error_code": e.code} for uid in bitrix_user_ids]}

    welcome_message = (getattr(portal, "welcome_message", None) or "").strip() or "Привет! Я Teachbase AI. Напишите «ping» — отвечу «pong»."

    start = time.monotonic()
    results: list[dict[str, Any]] = []

    def _send(uid: int) -> dict[str, Any]:
        dialog_id = str(uid)
        ok, err, _ = bitrix_client.imbot_message_add(
            domain,
            access_token,
            int(bot_id),
            dialog_id,
            welcome_message,
        )
        return {"user_id": uid, "ok": bool(ok), "error_code": "ok" if ok else (err or "send_failed")}

    with ThreadPoolExecutor(max_workers=PROVISION_MAX_WORKERS) as ex:
        futures = {ex.submit(_send, uid): uid for uid in bitrix_user_ids}
        for fut in as_completed(futures):
            if time.monotonic() - start > PROVISION_TIME_BUDGET_SEC:
                break
            try:
                results.append(fut.result())
            except Exception:
                uid = futures.get(fut, 0)
                results.append({"user_id": uid, "ok": False, "error_code": "exception"})

    done_ids = {r["user_id"] for r in results}
    for uid in bitrix_user_ids:
        if uid not in done_ids:
            results.append({"user_id": uid, "ok": False, "error_code": "timeout"})

    ok_count = sum(1 for r in results if r["ok"])
    fail_count = len(results) - ok_count
    return {"ok_count": ok_count, "fail_count": fail_count, "results": results}
