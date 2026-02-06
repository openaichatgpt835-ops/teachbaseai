"""Finalize install orchestration (allowlist -> ensure bot -> provision chats)."""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

WELCOME_IDEMPOTENCY_HOURS = 24

from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from apps.backend.config import get_settings
from apps.backend.models.event import Event
from apps.backend.models.portal import Portal, PortalUsersAccess
from apps.backend.services.portal_tokens import get_access_token
from apps.backend.services.bot_provisioning import ensure_bot_registered
from apps.backend.services.bitrix_logging import (
    log_outbound_prepare_chats,
    log_outbound_imbot_message_add,
)
from apps.backend.clients import bitrix as bitrix_client

# Бюджет времени и параллелизм
FINALIZE_TIME_BUDGET_SEC = 10


def _now_trace_id() -> str:
    return str(uuid.uuid4())[:16]


def _int_or_none(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _portal_meta(portal: Portal) -> dict[str, Any]:
    if not portal.metadata_json:
        return {}
    try:
        data = json.loads(portal.metadata_json)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_portal_meta(db: Session, portal: Portal, data: dict[str, Any]) -> None:
    portal.metadata_json = json.dumps(data, ensure_ascii=False)
    db.add(portal)
    db.commit()


def _log_step(
    db: Session,
    portal_id: int,
    trace_id: str,
    step: str,
    status: str,
    detail: dict[str, Any] | None = None,
) -> None:
    payload = {"trace_id": trace_id, "step": step, "status": status}
    if detail:
        payload.update(detail)
    db.add(Event(
        portal_id=portal_id,
        provider_event_id=trace_id,
        event_type="install_step",
        payload_json=json.dumps(payload, ensure_ascii=False),
    ))
    db.commit()


def step_save_allowlist(
    db: Session,
    portal_id: int,
    user_ids: list[int],
    created_by_bitrix_user_id: int | None = None,
) -> dict[str, Any]:
    created_by = _int_or_none(created_by_bitrix_user_id)
    db.execute(delete(PortalUsersAccess).where(PortalUsersAccess.portal_id == portal_id))
    for uid in user_ids:
        db.add(PortalUsersAccess(
            portal_id=portal_id,
            user_id=str(uid),
            created_by_bitrix_user_id=created_by,
        ))
    db.commit()
    return {"status": "ok", "count": len(user_ids)}


def _child_trace_id(parent_trace_id: str, user_id: int) -> str:
    return f"{parent_trace_id}-u{user_id}"[:64]


def _welcome_hash(msg: str) -> str:
    return hashlib.sha256((msg or "").encode("utf-8")).hexdigest()


def step_provision_chats(
    db: Session,
    portal_id: int,
    domain: str,
    access_token: str,
    bot_id: int,
    user_ids: list[int],
    trace_id: str,
    welcome_message: str | None = None,
    time_budget_sec: int = FINALIZE_TIME_BUDGET_SEC,
) -> dict[str, Any]:
    """
    Для каждого user_id: imbot.message.add(BOT_ID, DIALOG_ID=user_id, MESSAGE=welcome).
    Логируем каждый вызов imbot_message_add, в failed — bitrix_error_code/desc и trace_id_child.
    """
    start = time.monotonic()
    msg = (welcome_message or "").strip() or "Привет! Я Teachbase AI. Напишите «ping» — отвечу «pong»."
    welcome_hash = _welcome_hash(msg)
    cutoff = datetime.utcnow() - timedelta(hours=WELCOME_IDEMPOTENCY_HOURS)
    results: list[dict[str, Any]] = []
    child_trace_ids: list[str] = []

    for uid in user_ids:
        if time.monotonic() - start > time_budget_sec:
            results.append({
                "user_id": uid,
                "ok": False,
                "code": "timeout",
                "bitrix_error_code": None,
                "bitrix_error_desc": None,
                "trace_id_child": None,
            })
            continue
        child_tid = _child_trace_id(trace_id, uid)
        child_trace_ids.append(child_tid)

        access_row = db.execute(
            select(PortalUsersAccess).where(
                PortalUsersAccess.portal_id == portal_id,
                PortalUsersAccess.user_id == str(uid),
            )
        ).scalar_one_or_none()
        if access_row and getattr(access_row, "last_welcome_hash", None) == welcome_hash:
            last_at = getattr(access_row, "last_welcome_at", None)
            if last_at and last_at >= cutoff:
                results.append({
                    "user_id": uid,
                    "ok": True,
                    "code": "ok_skipped_idempotent",
                    "bitrix_error_code": None,
                    "bitrix_error_desc": None,
                    "trace_id_child": child_tid,
                })
                continue

        dialog_id = str(uid)
        t1 = time.perf_counter()
        msg_ok, msg_err, msg_desc = bitrix_client.imbot_message_add(
            domain,
            access_token,
            bot_id,
            dialog_id,
            msg,
        )
        msg_ms = int((time.perf_counter() - t1) * 1000)
        msg_status = 200 if (msg_ok and not msg_err) else 400
        log_outbound_imbot_message_add(
            db,
            child_tid,
            portal_id=portal_id,
            target_user_id=uid,
            dialog_id=dialog_id,
            status_code=msg_status,
            latency_ms=msg_ms,
            bitrix_error_code=msg_err,
            bitrix_error_desc=msg_desc or None,
            sent_keys=["BOT_ID", "DIALOG_ID", "MESSAGE"],
        )

        if not msg_ok:
            results.append({
                "user_id": uid,
                "ok": False,
                "code": msg_err or "message_add_failed",
                "bitrix_error_code": msg_err,
                "bitrix_error_desc": (msg_desc or "")[:200],
                "trace_id_child": child_tid,
            })
        else:
            if access_row:
                access_row.last_welcome_at = datetime.utcnow()
                access_row.last_welcome_hash = welcome_hash
                db.add(access_row)
                db.commit()
            results.append({
                "user_id": uid,
                "ok": True,
                "code": "ok",
                "bitrix_error_code": None,
                "bitrix_error_desc": None,
                "trace_id_child": child_tid,
            })

    ok = [r for r in results if r["ok"]]
    failed = [r for r in results if not r["ok"]]
    return {
        "status": "ok" if not failed else "partial_fail",
        "total": len(user_ids),
        "ok": len(ok),
        "failed": failed,
        "child_trace_ids": child_trace_ids,
    }


def finalize_install(
    db: Session,
    portal_id: int,
    selected_user_ids: list[int],
    auth_context: dict[str, Any],
    trace_id: str | None = None,
) -> dict[str, Any]:
    trace_id = trace_id or _now_trace_id()
    try:
        portal = db.execute(select(Portal).where(Portal.id == portal_id)).scalar_one_or_none()
        if not portal:
            return {"status": "error", "trace_id": trace_id, "error": "portal_not_found"}

        domain = (auth_context.get("domain") or portal.domain or "").strip()
        access_token = auth_context.get("access_token") or get_access_token(db, portal_id)
        created_by = _int_or_none(auth_context.get("user_id"))
        if not domain or not access_token:
            return {"status": "error", "trace_id": trace_id, "error": "missing_auth"}

        steps: dict[str, Any] = {}

        # Step A: allowlist (источник истины — БД)
        res_a = step_save_allowlist(db, portal_id, selected_user_ids, created_by)
        steps["allowlist"] = res_a.get("status", "error")
        _log_step(db, portal_id, trace_id, "allowlist", steps["allowlist"], {"count": res_a.get("count", 0)})

        # user_ids для prepare_chats — только из сохранённого allowlist (БД)
        allowlist_rows = db.execute(
            select(PortalUsersAccess.user_id).where(PortalUsersAccess.portal_id == portal_id)
        ).scalars().all()
        provision_user_ids = []
        for (uid,) in allowlist_rows:
            try:
                provision_user_ids.append(int(uid))
            except (TypeError, ValueError):
                pass
        logger.info(
            "finalize_install trace_id=%s portal_id=%s selected_count=%s provision_user_ids=%s",
            trace_id, portal_id, len(selected_user_ids), provision_user_ids,
        )

        # Step B: ensure bot (идемпотентно: bot.list -> при необходимости register)
        bot_result = ensure_bot_registered(
            db,
            portal_id,
            trace_id,
            domain=domain,
            access_token=access_token,
            force=False,
        )
        if not bot_result.get("ok"):
            err_code = bot_result.get("error_code") or "bot_not_registered"
            err_detail = (bot_result.get("error_detail_safe") or "")[:200]
            _log_step(db, portal_id, trace_id, "ensure_bot", "error", {
                "error": err_code,
                "error_detail_safe": err_detail,
                "trace_id": trace_id,
            })
            return {
                "status": "error",
                "trace_id": trace_id,
                "steps": steps,
                "error": err_code,
                "error_detail_safe": err_detail,
            }
        steps["ensure_bot"] = "ok"
        bot_id = _int_or_none(bot_result.get("bot_id")) or 0
        if not bot_id:
            _log_step(db, portal_id, trace_id, "ensure_bot", "error", {"error": "bot_id_missing_after_ensure"})
            return {"status": "error", "trace_id": trace_id, "steps": steps, "error": "bot_id_missing_after_ensure"}

        # Step C: provision chats только если allowlist непустой (imbot.chat.add + imbot.message.add)
        if not provision_user_ids:
            res_c = {
                "status": "skipped",
                "total": 0,
                "ok": 0,
                "failed": [],
                "child_trace_ids": [],
            }
            steps["provision"] = res_c
            _log_step(db, portal_id, trace_id, "provision", "skipped", {"reason": "allowlist_empty"})
        else:
            welcome_msg = (getattr(portal, "welcome_message", None) or "").strip() or "Привет! Я Teachbase AI. Напишите «ping» — отвечу «pong»."
            res_c = step_provision_chats(
                db,
                portal_id,
                domain,
                access_token,
                bot_id,
                provision_user_ids,
                trace_id,
                welcome_message=welcome_msg,
            )
            steps["provision"] = res_c
            _log_step(db, portal_id, trace_id, "provision", res_c.get("status", "error"), {
                "total": res_c.get("total"),
                "ok": res_c.get("ok"),
                "failed": res_c.get("failed", []),
            })
            log_outbound_prepare_chats(
                db,
                trace_id,
                portal_id,
                status=res_c.get("status", "error"),
                total=res_c.get("total", 0),
                ok_count=res_c.get("ok", 0),
                failed=res_c.get("failed"),
                child_trace_ids=res_c.get("child_trace_ids"),
            )

        status = "ok" if res_c.get("status") in ("ok", "skipped") else "partial_fail"
        return {"status": status, "trace_id": trace_id, "steps": steps}
    except Exception as e:
        # Никогда не пробрасывать — возвращаем JSON с кодом (глобальный handler тоже вернёт JSON при raise)
        err_msg = str(e)[:200].replace("'", "")
        return {"status": "error", "trace_id": trace_id, "error": "internal_error", "detail": err_msg}
