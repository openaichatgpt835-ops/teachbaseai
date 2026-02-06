"""Идемпотентная регистрация бота (imbot.register). Секреты только в БД."""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.backend.config import get_settings
from apps.backend.models.event import Event
from apps.backend.models.portal import Portal
from apps.backend.services.portal_tokens import ensure_fresh_access_token, refresh_portal_tokens, BitrixAuthError
from apps.backend.services.bitrix_auth import rest_call_with_refresh
from apps.backend.services.token_crypto import encrypt_token
from apps.backend.services.bitrix_logging import (
    log_outbound_imbot_register,
    log_outbound_imbot_update,
    log_outbound_imbot_unregister,
)
from apps.backend.clients import bitrix as bitrix_client

logger = logging.getLogger(__name__)

# Единый CODE бота (как в bitrix.py BOT_CODE_DEFAULT)
BOT_CODE = getattr(bitrix_client, "BOT_CODE_DEFAULT", "teachbase_assistant")


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


def _bot_id_from_register_response(data: dict | None) -> int | None:
    """Извлечь bot_id из ответа imbot.register. Bitrix может вернуть result (число) или bot_id/BOT_ID."""
    if not data:
        return None
    v = data.get("bot_id") or data.get("BOT_ID")
    if v is not None:
        try:
            return int(v)
        except (TypeError, ValueError):
            pass
    v = data.get("result")
    if isinstance(v, int):
        return v
    if v is not None:
        try:
            return int(v)
        except (TypeError, ValueError):
            pass
    return None


def _find_bot_by_code_or_id(bots: list[dict], bot_id: int | None, code: str) -> dict | None:
    """Найти бота по id или по полю code/CODE. Bitrix может вернуть ID или BOT_ID."""
    for b in bots:
        if not isinstance(b, dict):
            continue
        bid = b.get("BOT_ID") or b.get("bot_id") or b.get("id") or b.get("ID")
        if bid is not None and bot_id is not None:
            try:
                if int(bid) == int(bot_id):
                    return b
            except (TypeError, ValueError):
                pass
        bc = (b.get("code") or b.get("CODE") or "").strip()
        if bc and code and bc == code:
            return b
    return None


def _bot_id_from_bot_dict(b: dict) -> int | None:
    """Извлечь числовой bot_id из элемента imbot.bot.list."""
    v = b.get("BOT_ID") or b.get("bot_id") or b.get("ID") or b.get("id")
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def ensure_bot_handlers(
    db: Session,
    portal_id: int,
    trace_id: str,
) -> dict[str, Any]:
    """
    Устанавливает handler URLs у бота (EVENT_MESSAGE_ADD и др.) через imbot.update.
    Сначала imbot.bot.list, ищем бота по CODE или bot_id из БД; если не найден — not_found.
    Возвращает {ok, bot_id, error_code?, event_urls_sent, notes}.
    """
    from apps.backend.models.portal import Portal
    portal = db.get(Portal, portal_id)
    if not portal:
        return {"ok": False, "error_code": "portal_not_found", "event_urls_sent": [], "notes": "Portal not found"}
    domain = (portal.domain or "").strip()
    domain_full = f"https://{domain}" if domain and not domain.startswith("http") else (domain or None)
    if not domain_full:
        return {"ok": False, "error_code": "missing_auth", "event_urls_sent": [], "notes": "No domain or token"}
    settings = get_settings()
    base = (settings.public_base_url or "").strip().rstrip("/")
    if not base:
        return {"ok": False, "error_code": "public_base_url_not_configured", "event_urls_sent": [], "notes": "PUBLIC_BASE_URL not set"}
    events_url = f"{base}/v1/bitrix/events"
    t0 = time.perf_counter()
    result, list_err, list_err_desc, list_status, _ = rest_call_with_refresh(
        db, portal_id, "imbot.bot.list", {}, trace_id, timeout_sec=10
    )
    _ = int((time.perf_counter() - t0) * 1000)
    if list_err or not result:
        return {
            "ok": False,
            "error_code": list_err or "rest_error",
            "event_urls_sent": [],
            "notes": (list_err_desc or "imbot.bot.list failed")[:200],
        }
    bots = bitrix_client._normalize_bot_list_result(result)
    meta = _portal_meta(portal)
    our_bot_id = meta.get("bot_id")
    bot = _find_bot_by_code_or_id(bots, our_bot_id, BOT_CODE)
    if not bot:
        return {
            "ok": False,
            "error_code": "not_found",
            "event_urls_sent": [],
            "notes": "Bot not found in imbot.bot.list by CODE or bot_id",
            "bots_count": len(bots),
        }
    bid = _bot_id_from_bot_dict(bot)
    if bid is None:
        return {"ok": False, "error_code": "bot_id_missing", "event_urls_sent": [], "notes": "Bot entry has no ID"}
    name = (bot.get("NAME") or bot.get("name") or bitrix_client.BOT_NAME_DEFAULT or "Teachbase Ассистент")[:64]
    update_params = {
        "BOT_ID": str(bid),
        "FIELDS[CODE]": BOT_CODE,
        "FIELDS[EVENT_MESSAGE_ADD]": events_url,
        "FIELDS[EVENT_WELCOME_MESSAGE]": events_url,
        "FIELDS[EVENT_BOT_DELETE]": events_url,
        "FIELDS[PROPERTIES][NAME]": name,
        "FIELDS[PROPERTIES][LAST_NAME]": "",
    }
    t0 = time.perf_counter()
    data, err, err_desc, status_code, _ = rest_call_with_refresh(
        db, portal_id, "imbot.update", update_params, trace_id, timeout_sec=15
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)
    event_urls_sent = [events_url]
    log_outbound_imbot_update(
        db, trace_id, portal_id, bid,
        status_code=status_code, latency_ms=latency_ms,
        bitrix_error_code=err,
        bitrix_error_desc=err_desc or None,
        event_urls_sent=event_urls_sent,
    )
    if err or (data is not None and data.get("error")):
        return {
            "ok": False,
            "bot_id": bid,
            "error_code": err or (data.get("error") if data else "unknown"),
            "event_urls_sent": event_urls_sent,
            "notes": (err_desc or "")[:200],
        }
    return {
        "ok": True,
        "bot_id": bid,
        "event_urls_sent": event_urls_sent,
        "notes": "imbot.update success",
    }


# Коды ботов, которых мы считаем «нашими» при сбросе (только эти удаляем).
OUR_BOT_CODES = {BOT_CODE}


def reset_portal_bot(
    db: Session,
    portal_id: int,
    trace_id: str,
) -> dict[str, Any]:
    """
    Безопасный сброс: удалить только наших ботов (CODE in OUR_BOT_CODES), затем register + fix handlers.
    Если кандидатов > 3 — не удаляем (защита), возвращаем too_many_candidates.
    Возвращает {ok, deleted_count, registered_bot_id, trace_id, notes, error_code?, sample_bots?}.
    """
    portal = db.get(Portal, portal_id)
    if not portal:
        return {"ok": False, "deleted_count": 0, "registered_bot_id": None, "trace_id": trace_id, "notes": "Portal not found", "error_code": "portal_not_found"}
    domain = (portal.domain or "").strip()
    domain_full = f"https://{domain}" if domain and not domain.startswith("http") else (domain or None)
    if not domain_full:
        return {"ok": False, "deleted_count": 0, "registered_bot_id": None, "trace_id": trace_id, "notes": "No domain", "error_code": "missing_auth"}
    try:
        access_token = ensure_fresh_access_token(db, portal_id, trace_id=trace_id)
    except BitrixAuthError as e:
        return {
            "ok": False,
            "deleted_count": 0,
            "registered_bot_id": None,
            "trace_id": trace_id,
            "notes": e.detail,
            "error_code": e.code,
        }
    bots, list_err = bitrix_client.imbot_bot_list(domain_full, access_token)
    if list_err:
        return {"ok": False, "deleted_count": 0, "registered_bot_id": None, "trace_id": trace_id, "notes": f"imbot.bot.list failed: {list_err}", "error_code": list_err}
    candidates = []
    for b in bots:
        if not isinstance(b, dict):
            continue
        code = (b.get("CODE") or b.get("code") or "").strip()
        if code in OUR_BOT_CODES:
            candidates.append(b)
    if len(candidates) > 3:
        sample = [{"id": _bot_id_from_bot_dict(b), "code": (b.get("CODE") or b.get("code") or "")[:32], "name": (b.get("NAME") or b.get("name") or "")[:64]} for b in candidates[:5]]
        return {
            "ok": False,
            "deleted_count": 0,
            "registered_bot_id": None,
            "trace_id": trace_id,
            "notes": "too_many_candidates",
            "error_code": "too_many_candidates",
            "sample_bots": sample,
        }
    deleted_count = 0
    for b in candidates:
        bid = _bot_id_from_bot_dict(b)
        if bid is None:
            continue
        t0 = time.perf_counter()
        data, err, err_desc, status_code = bitrix_client.imbot_unregister(domain_full, access_token, bid)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        log_outbound_imbot_unregister(
            db, trace_id, portal_id, bid,
            status_code=status_code,
            bitrix_error_code=err,
            bitrix_error_desc=err_desc or None,
        )
        if not err and (data is None or not data.get("error")):
            deleted_count += 1
    meta = _portal_meta(portal)
    meta.pop("bot_id", None)
    meta.pop("bot_app_token_enc", None)
    _save_portal_meta(db, portal, meta)
    reg = ensure_bot_registered(db, portal_id, trace_id, force=True)
    if not reg.get("ok"):
        return {
            "ok": False,
            "deleted_count": deleted_count,
            "registered_bot_id": None,
            "trace_id": trace_id,
            "notes": reg.get("error_detail_safe") or reg.get("error_code") or "ensure_bot_registered failed",
            "error_code": reg.get("error_code"),
        }
    new_bot_id = reg.get("bot_id")
    fix = ensure_bot_handlers(db, portal_id, trace_id)
    if not fix.get("ok"):
        return {
            "ok": True,
            "deleted_count": deleted_count,
            "registered_bot_id": new_bot_id,
            "trace_id": trace_id,
            "notes": f"Registered bot_id={new_bot_id}; fix-handlers failed: {fix.get('error_code')}",
        }
    return {
        "ok": True,
        "deleted_count": deleted_count,
        "registered_bot_id": new_bot_id,
        "trace_id": trace_id,
        "notes": f"Deleted {deleted_count} bot(s), registered bot_id={new_bot_id}, handlers updated.",
    }


def ensure_bot_registered(
    db: Session,
    portal_id: int,
    trace_id: str,
    *,
    domain: str | None = None,
    access_token: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """
    Идемпотентно (если не force):
    1) Если в БД есть bot_id — вызываем imbot.bot.list; если бот найден — возвращаем OK без register.
    2) Если bot_id нет — вызываем imbot.bot.list и ищем бота по CODE; если найден — сохраняем bot_id и возвращаем OK.
    3) Только если бот не найден — вызываем imbot.register, извлекаем bot_id (в т.ч. из result), сохраняем.
    Возвращает {ok, bot_id, application_token_present, error_code?, error_detail_safe?, event_urls_sent}.
    """
    result: dict[str, Any] = {
        "ok": False,
        "bot_id": None,
        "application_token_present": False,
        "error_code": None,
        "error_detail_safe": None,
        "event_urls_sent": [],
    }
    portal = db.execute(select(Portal).where(Portal.id == portal_id)).scalar_one_or_none()
    if not portal:
        result["error_code"] = "portal_not_found"
        result["error_detail_safe"] = "portal_id not in DB"
        return result

    s = get_settings()
    events_base = (s.public_base_url or "").strip()
    if not events_base or not events_base.startswith("http"):
        result["error_code"] = "public_base_url_not_configured"
        result["error_detail_safe"] = "PUBLIC_BASE_URL must be set (HTTPS) for bot registration"
        logger.info(
            "bitrix_install_xhr trace_id=%s portal_id=%s step=ensure_bot err_code=public_base_url_not_configured",
            trace_id, portal_id,
        )
        return result

    domain_str = (domain or portal.domain or "").strip()
    if not domain_str:
        result["error_code"] = "missing_auth"
        result["error_detail_safe"] = "domain or access_token missing"
        return result
    try:
        token = access_token or ensure_fresh_access_token(db, portal_id, trace_id=trace_id)
    except BitrixAuthError as e:
        result["error_code"] = e.code
        result["error_detail_safe"] = e.detail
        return result

    meta = _portal_meta(portal)
    stored_bot_id = meta.get("bot_id")
    if stored_bot_id is not None:
        try:
            stored_bot_id = int(stored_bot_id)
        except (TypeError, ValueError):
            stored_bot_id = None

    # Шаг 1: если есть bot_id и не force — проверяем через imbot.bot.list
    if not force and stored_bot_id is not None:
        list_result, list_err, list_err_desc, _, _ = rest_call_with_refresh(
            db, portal_id, "imbot.bot.list", {}, trace_id, timeout_sec=10
        )
        bots = bitrix_client._normalize_bot_list_result(list_result)
        if not list_err and bots:
            found = _find_bot_by_code_or_id(bots, stored_bot_id, BOT_CODE)
            if found:
                bid = found.get("id") or found.get("ID")
                if bid is not None:
                    try:
                        result["bot_id"] = int(bid)
                    except (TypeError, ValueError):
                        result["bot_id"] = stored_bot_id
                else:
                    result["bot_id"] = stored_bot_id
                result["ok"] = True
                result["application_token_present"] = bool(meta.get("bot_app_token_enc"))
                result["event_urls_sent"] = []
                logger.info(
                    "bitrix_install_xhr trace_id=%s portal_id=%s step=ensure_bot status=ok idempotent bot_list bot_id=%s",
                    trace_id, portal_id, result["bot_id"],
                )
                return result
        # bot_list не нашёл — возможно бот удалён; продолжаем к register

    # Шаг 2: нет bot_id или не найден в list — ищем по CODE в imbot.bot.list
    if not force:
        list_result, list_err, list_err_desc, _, _ = rest_call_with_refresh(
            db, portal_id, "imbot.bot.list", {}, trace_id, timeout_sec=10
        )
        bots = bitrix_client._normalize_bot_list_result(list_result)
        if not list_err and bots:
            found = _find_bot_by_code_or_id(bots, stored_bot_id, BOT_CODE)
            if found:
                bid = found.get("id") or found.get("ID")
                if bid is not None:
                    try:
                        bot_id_val = int(bid)
                        meta["bot_id"] = bot_id_val
                        _save_portal_meta(db, portal, meta)
                        result["ok"] = True
                        result["bot_id"] = bot_id_val
                        result["application_token_present"] = bool(meta.get("bot_app_token_enc"))
                        result["event_urls_sent"] = []
                        logger.info(
                            "bitrix_install_xhr trace_id=%s portal_id=%s step=ensure_bot status=ok found_by_code bot_id=%s",
                            trace_id, portal_id, bot_id_val,
                        )
                        return result
                    except (TypeError, ValueError):
                        pass

    # Шаг 3: регистрируем бота
    data, err, err_desc, event_urls_sent, http_status, time_ms, request_shape = bitrix_client.imbot_register(
        domain_str,
        token,
        events_base_url=events_base,
        trace_id=trace_id,
        portal_id=portal_id,
    )
    if err == bitrix_client.BITRIX_ERR_AUTH_INVALID:
        try:
            refreshed = refresh_portal_tokens(db, portal_id, trace_id=trace_id)
            token = refreshed.get("access_token", token)
            data, err, err_desc, event_urls_sent, http_status, time_ms, request_shape = bitrix_client.imbot_register(
                domain_str,
                token,
                events_base_url=events_base,
                trace_id=trace_id,
                portal_id=portal_id,
            )
        except BitrixAuthError as e:
            result["error_code"] = "bitrix_refresh_failed"
            result["error_detail_safe"] = e.detail
            return result
    result["event_urls_sent"] = event_urls_sent or []
    bot_id_after = _bot_id_from_register_response(data)
    response_shape = {
        "http_status": http_status,
        "bitrix_error_code": err,
        "bitrix_error_desc": (err_desc or "")[:200] if err_desc else None,
        "bot_id": bot_id_after,
    }
    log_outbound_imbot_register(
        db,
        trace_id,
        portal_id,
        status_code=http_status,
        latency_ms=time_ms,
        error_code=err,
        error_description_safe=err_desc or None,
        event_urls_sent=event_urls_sent or None,
        request_shape=request_shape if request_shape is not None else None,
        response_shape=response_shape,
    )
    if err:
        result["error_code"] = err
        result["error_detail_safe"] = err_desc or err
        logger.info(
            "bitrix_install_xhr trace_id=%s portal_id=%s step=ensure_bot bitrix_method=imbot.register err_code=%s",
            trace_id, portal_id, err,
        )
        db.add(Event(
            portal_id=portal_id,
            provider_event_id=trace_id,
            event_type="install_step",
            payload_json=json.dumps({
                "trace_id": trace_id,
                "step": "ensure_bot",
                "status": "error",
                "error_code": err,
                "error_description_safe": (err_desc or "")[:200],
                "event_urls_sent": result["event_urls_sent"],
            }, ensure_ascii=False),
        ))
        db.commit()
        return result

    if not data or data.get("error"):
        result["error_code"] = "bot_register_failed"
        result["error_detail_safe"] = err_desc or (data.get("error_description") if data else None) or (data.get("error") if data else "unknown")
        if isinstance(result["error_detail_safe"], str):
            result["error_detail_safe"] = result["error_detail_safe"][:200]
        logger.info(
            "bitrix_install_xhr trace_id=%s portal_id=%s step=ensure_bot bitrix_method=imbot.register err_code=bot_register_failed",
            trace_id, portal_id,
        )
        return result

    bot_id = bot_id_after
    app_token = (data.get("app_token") or data.get("APP_TOKEN") or "") if data else ""
    enc_key = s.token_encryption_key or s.secret_key
    if bot_id is not None:
        meta["bot_id"] = int(bot_id)
    if app_token and enc_key:
        meta["bot_app_token_enc"] = encrypt_token(str(app_token), enc_key)
    _save_portal_meta(db, portal, meta)

    result["ok"] = True
    result["bot_id"] = int(bot_id) if bot_id is not None else None
    result["application_token_present"] = bool(app_token)
    result["event_urls_sent"] = event_urls_sent or []
    logger.info(
        "bitrix_install_xhr trace_id=%s portal_id=%s step=ensure_bot bitrix_method=imbot.register status=ok bot_id=%s",
        trace_id, portal_id, result["bot_id"],
    )
    db.add(Event(
        portal_id=portal_id,
        provider_event_id=trace_id,
        event_type="install_step",
        payload_json=json.dumps({
            "trace_id": trace_id,
            "step": "ensure_bot",
            "status": "ok",
            "bot_id": result["bot_id"],
            "event_urls_sent": result["event_urls_sent"],
        }, ensure_ascii=False),
    ))
    db.commit()
    return result
