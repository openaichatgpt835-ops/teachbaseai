"""Bitrix HTTP trace logging."""
import json
import logging
import time
import uuid
from typing import Any

from sqlalchemy.orm import Session

from apps.backend.models.bitrix_log import BitrixHttpLog

logger = logging.getLogger(__name__)


def _mask_secrets(obj: dict) -> dict:
    out = {}
    secret_keys = {"access_token", "refresh_token", "auth", "AUTH", "auth_id", "refresh_id"}
    for k, v in obj.items():
        key_lower = k.lower() if isinstance(k, str) else ""
        if key_lower in secret_keys or "token" in key_lower or "secret" in key_lower:
            out[k] = "[MASKED]" if v else None
        elif isinstance(v, dict):
            out[k] = _mask_secrets(v)
        else:
            out[k] = v
    return out


def log_inbound(
    db: Session,
    trace_id: str,
    method: str,
    path: str,
    query_keys: list[str],
    body_keys: list[str],
    status_code: int,
    latency_ms: int,
    portal_id: int | None = None,
    accept: str | None = None,
    sec_fetch_dest: str | None = None,
    sec_fetch_mode: str | None = None,
    user_agent: str | None = None,
    response_content_type: str | None = None,
    response_length: int | None = None,
    response_is_json: bool | None = None,
    request_json: dict | list | None = None,
    response_json: dict | list | None = None,
    headers_min: dict | None = None,
) -> None:
    summary = {
        "query_keys": query_keys,
        "body_keys": body_keys,
        "accept": (accept or "")[:256],
        "sec_fetch_dest": (sec_fetch_dest or "")[:64],
        "sec_fetch_mode": (sec_fetch_mode or "")[:64],
        "user_agent": (user_agent or "")[:256],
        "response_content_type": (response_content_type or "")[:128],
        "response_length": response_length,
        "response_is_json": response_is_json,
    }
    if request_json is not None:
        summary["request_json"] = request_json
    if response_json is not None:
        summary["response_json"] = response_json
    if headers_min is not None:
        summary["headers_min"] = headers_min
    row = BitrixHttpLog(
        trace_id=trace_id,
        portal_id=portal_id,
        direction="inbound",
        kind="request",
        method=method,
        path=path,
        summary_json=json.dumps(summary),
        status_code=status_code,
        latency_ms=latency_ms,
    )
    db.add(row)
    db.commit()
    logger.info(
        "bitrix_inbound trace_id=%s method=%s path=%s status=%d latency_ms=%d content_type=%s",
        trace_id, method, path, status_code, latency_ms,
        response_content_type or "-",
    )


def log_outbound(
    db: Session,
    trace_id: str,
    portal_id: int | None,
    method: str,
    rest_method: str,
    status_code: int,
    latency_ms: int,
    retry_count: int = 0,
) -> None:
    summary = {"rest_method": rest_method, "retry_count": retry_count}
    row = BitrixHttpLog(
        trace_id=trace_id,
        portal_id=portal_id,
        direction="outbound",
        kind="rest_call",
        method=method,
        path=rest_method,
        summary_json=json.dumps(summary),
        status_code=status_code,
        latency_ms=latency_ms,
    )
    db.add(row)
    db.commit()
    logger.info(
        "bitrix_outbound trace_id=%s rest_method=%s status=%d latency_ms=%d",
        trace_id, rest_method, status_code, latency_ms,
    )


def log_outbound_imbot_register(
    db: Session,
    trace_id: str,
    portal_id: int,
    status_code: int,
    latency_ms: int,
    error_code: str | None = None,
    error_description_safe: str | None = None,
    event_urls_sent: list[str] | None = None,
    request_shape: dict[str, Any] | None = None,
    response_shape: dict[str, Any] | None = None,
) -> None:
    """Доказательное сохранение вызова imbot.register в bitrix_http_logs (без секретов)."""
    summary: dict[str, Any] = {
        "rest_method": "imbot.register",
        "retry_count": 0,
    }
    if error_code is not None:
        summary["error_code"] = error_code
    if error_description_safe is not None:
        summary["error_description_safe"] = (error_description_safe or "")[:200]
    if event_urls_sent is not None:
        summary["event_urls_sent"] = list(event_urls_sent)
    if request_shape is not None:
        summary["request_shape_json"] = request_shape
    if response_shape is not None:
        summary["response_shape_json"] = response_shape
    row = BitrixHttpLog(
        trace_id=trace_id,
        portal_id=portal_id,
        direction="outbound",
        kind="imbot_register",
        method="POST",
        path="imbot.register",
        summary_json=json.dumps(summary),
        status_code=status_code or None,
        latency_ms=latency_ms or None,
    )
    db.add(row)
    db.commit()
    logger.info(
        "bitrix_outbound_imbot_register trace_id=%s portal_id=%s status=%s err=%s",
        trace_id, portal_id, status_code, error_code or "ok",
    )


def log_outbound_imbot_bot_list(
    db: Session,
    trace_id: str,
    portal_id: int | None,
    status_code: int,
    latency_ms: int,
    bitrix_error_code: str | None = None,
    bitrix_error_desc: str | None = None,
    bots_count: int = 0,
    found_by: str | None = None,
    sample_bots: list[dict] | None = None,
    refreshed: bool | None = None,
) -> None:
    """Диагностика imbot.bot.list: status, error, bots_count, found_by, sample_bots (без токенов)."""
    summary: dict[str, Any] = {
        "rest_method": "imbot.bot.list",
        "status_code": status_code,
        "latency_ms": latency_ms,
        "bots_count": bots_count,
    }
    if bitrix_error_code is not None:
        summary["bitrix_error_code"] = bitrix_error_code
    if bitrix_error_desc is not None:
        summary["bitrix_error_desc"] = (bitrix_error_desc or "")[:200]
    if found_by is not None:
        summary["found_by"] = found_by
    if sample_bots is not None:
        summary["sample_bots"] = list(sample_bots)[:5]
    if refreshed is not None:
        summary["refreshed"] = bool(refreshed)
    row = BitrixHttpLog(
        trace_id=trace_id,
        portal_id=portal_id,
        direction="outbound",
        kind="imbot_bot_list",
        method="POST",
        path="imbot.bot.list",
        summary_json=json.dumps(summary),
        status_code=status_code,
        latency_ms=latency_ms,
    )
    db.add(row)
    db.commit()
    logger.info(
        "bitrix_outbound_imbot_bot_list trace_id=%s portal_id=%s status=%s bots_count=%s found_by=%s",
        trace_id, portal_id, status_code, bots_count, found_by or "-",
    )


def log_outbound_imbot_update(
    db: Session,
    trace_id: str,
    portal_id: int,
    bot_id: int,
    status_code: int,
    latency_ms: int,
    bitrix_error_code: str | None = None,
    bitrix_error_desc: str | None = None,
    event_urls_sent: list[str] | None = None,
) -> None:
    """Лог вызова imbot.update (без токенов). kind=imbot_update."""
    summary: dict[str, Any] = {
        "rest_method": "imbot.update",
        "bot_id": bot_id,
        "status_code": status_code,
        "latency_ms": latency_ms,
    }
    if bitrix_error_code is not None:
        summary["bitrix_error_code"] = bitrix_error_code
    if bitrix_error_desc is not None:
        summary["bitrix_error_desc"] = (bitrix_error_desc or "")[:200]
    if event_urls_sent is not None:
        summary["event_urls_sent"] = list(event_urls_sent)
    row = BitrixHttpLog(
        trace_id=trace_id,
        portal_id=portal_id,
        direction="outbound",
        kind="imbot_update",
        method="POST",
        path="imbot.update",
        summary_json=json.dumps(summary),
        status_code=status_code,
        latency_ms=latency_ms,
    )
    db.add(row)
    db.commit()
    logger.info(
        "bitrix_outbound_imbot_update trace_id=%s portal_id=%s bot_id=%s status=%s err=%s",
        trace_id, portal_id, bot_id, status_code, bitrix_error_code or "ok",
    )


def log_outbound_imbot_unregister(
    db: Session,
    trace_id: str,
    portal_id: int,
    bot_id: int,
    status_code: int,
    bitrix_error_code: str | None = None,
    bitrix_error_desc: str | None = None,
) -> None:
    """Лог вызова imbot.unregister (без токенов). kind=imbot_unregister."""
    summary: dict[str, Any] = {
        "rest_method": "imbot.unregister",
        "bot_id": bot_id,
        "status_code": status_code,
    }
    if bitrix_error_code is not None:
        summary["bitrix_error_code"] = bitrix_error_code
    if bitrix_error_desc is not None:
        summary["bitrix_error_desc"] = (bitrix_error_desc or "")[:200]
    row = BitrixHttpLog(
        trace_id=trace_id,
        portal_id=portal_id,
        direction="outbound",
        kind="imbot_unregister",
        method="POST",
        path="imbot.unregister",
        summary_json=json.dumps(summary),
        status_code=status_code,
        latency_ms=None,
    )
    db.add(row)
    db.commit()
    logger.info(
        "bitrix_outbound_imbot_unregister trace_id=%s portal_id=%s bot_id=%s status=%s err=%s",
        trace_id, portal_id, bot_id, status_code, bitrix_error_code or "ok",
    )


def log_outbound_imbot_chat_add(
    db: Session,
    trace_id: str,
    portal_id: int,
    target_user_id: int,
    chat_id: int | None,
    status_code: int,
    latency_ms: int,
    bitrix_error_code: str | None = None,
    bitrix_error_desc: str | None = None,
    sent_keys: list[str] | None = None,
) -> None:
    """Лог вызова imbot.chat.add (без токенов). kind=imbot_chat_add."""
    summary: dict[str, Any] = {
        "rest_method": "imbot.chat.add",
        "target_user_id": target_user_id,
        "chat_id": chat_id,
        "status_code": status_code,
        "latency_ms": latency_ms,
    }
    if bitrix_error_code is not None:
        summary["bitrix_error_code"] = bitrix_error_code
    if bitrix_error_desc is not None:
        summary["bitrix_error_desc"] = (bitrix_error_desc or "")[:200]
    if sent_keys is not None:
        summary["sent_keys"] = sent_keys
    row = BitrixHttpLog(
        trace_id=trace_id,
        portal_id=portal_id,
        direction="outbound",
        kind="imbot_chat_add",
        method="POST",
        path="imbot.chat.add",
        summary_json=json.dumps(summary),
        status_code=status_code,
        latency_ms=latency_ms,
    )
    db.add(row)
    db.commit()
    logger.info(
        "bitrix_outbound_imbot_chat_add trace_id=%s portal_id=%s user_id=%s chat_id=%s status=%s err=%s",
        trace_id, portal_id, target_user_id, chat_id, status_code, bitrix_error_code or "ok",
    )


def log_outbound_imbot_message_add(
    db: Session,
    trace_id: str,
    portal_id: int,
    target_user_id: int | None,
    dialog_id: str,
    status_code: int,
    latency_ms: int,
    bitrix_error_code: str | None = None,
    bitrix_error_desc: str | None = None,
    sent_keys: list[str] | None = None,
) -> None:
    """Лог вызова imbot.message.add (без токенов). kind=imbot_message_add."""
    summary: dict[str, Any] = {
        "rest_method": "imbot.message.add",
        "target_user_id": target_user_id,
        "dialog_id": (dialog_id or "")[:64],
        "status_code": status_code,
        "latency_ms": latency_ms,
    }
    if bitrix_error_code is not None:
        summary["bitrix_error_code"] = bitrix_error_code
    if bitrix_error_desc is not None:
        summary["bitrix_error_desc"] = (bitrix_error_desc or "")[:200]
    if sent_keys is not None:
        summary["sent_keys"] = sent_keys
    row = BitrixHttpLog(
        trace_id=trace_id,
        portal_id=portal_id,
        direction="outbound",
        kind="imbot_message_add",
        method="POST",
        path="imbot.message.add",
        summary_json=json.dumps(summary),
        status_code=status_code,
        latency_ms=latency_ms,
    )
    db.add(row)
    db.commit()
    logger.info(
        "bitrix_outbound_imbot_message_add trace_id=%s portal_id=%s dialog_id=%s status=%s err=%s",
        trace_id, portal_id, (dialog_id or "")[:32], status_code, bitrix_error_code or "ok",
    )


def log_outbound_prepare_chats(
    db: Session,
    trace_id: str,
    portal_id: int,
    status: str,
    total: int,
    ok_count: int,
    failed: list[dict] | None = None,
    latency_ms: int | None = None,
    child_trace_ids: list[str] | None = None,
) -> None:
    """Лог результата шага prepare chats (без токенов). kind=prepare_chats. failed: user_id, code, bitrix_error_code, bitrix_error_desc, trace_id_child."""
    summary: dict[str, Any] = {
        "rest_method": "prepare_chats",
        "status": status,
        "total": total,
        "ok_count": ok_count,
        "users_ok": ok_count,
        "users_failed": len(failed) if failed else 0,
    }
    if failed is not None:
        summary["failed"] = [
            {
                "user_id": f.get("user_id"),
                "code": f.get("code"),
                "bitrix_error_code": f.get("bitrix_error_code"),
                "bitrix_error_desc": f.get("bitrix_error_desc"),
                "trace_id_child": f.get("trace_id_child"),
            }
            for f in failed
        ]
    if child_trace_ids is not None:
        summary["child_trace_ids"] = child_trace_ids
    row = BitrixHttpLog(
        trace_id=trace_id,
        portal_id=portal_id,
        direction="outbound",
        kind="prepare_chats",
        method="POST",
        path="prepare_chats",
        summary_json=json.dumps(summary),
        status_code=200,
        latency_ms=latency_ms,
    )
    db.add(row)
    db.commit()
    logger.info(
        "bitrix_outbound_prepare_chats trace_id=%s portal_id=%s status=%s total=%s ok=%s",
        trace_id, portal_id, status, total, ok_count,
    )


def log_outbound_oauth_refresh(
    db: Session,
    trace_id: str,
    portal_id: int,
    status_code: int,
    latency_ms: int,
    error_code: str | None = None,
    error_description_safe: str | None = None,
    access_len: int | None = None,
    refresh_len: int | None = None,
    access_md5: str | None = None,
    refresh_md5: str | None = None,
    credentials_source: str | None = None,
    tokens_updated: bool | None = None,
) -> None:
    """Лог обновления токенов (oauth refresh) без секретов."""
    summary: dict[str, Any] = {
        "rest_method": "oauth.refresh",
        "status_code": status_code,
        "latency_ms": latency_ms,
        "access_len": access_len,
        "refresh_len": refresh_len,
        "access_md5": access_md5,
        "refresh_md5": refresh_md5,
    }
    if error_code:
        summary["error_code"] = error_code
    if error_description_safe:
        summary["error_description_safe"] = (error_description_safe or "")[:200]
    if credentials_source:
        summary["credentials_source"] = credentials_source
    if tokens_updated is not None:
        summary["tokens_updated"] = bool(tokens_updated)
    row = BitrixHttpLog(
        trace_id=trace_id,
        portal_id=portal_id,
        direction="outbound",
        kind="oauth_refresh",
        method="POST",
        path="oauth/token",
        summary_json=json.dumps(summary),
        status_code=status_code,
        latency_ms=latency_ms,
    )
    db.add(row)
    db.commit()
    logger.info(
        "bitrix_outbound_oauth_refresh trace_id=%s portal_id=%s status=%s err=%s",
        trace_id, portal_id, status_code, error_code or "ok",
    )
