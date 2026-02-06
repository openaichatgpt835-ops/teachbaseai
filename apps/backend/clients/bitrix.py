"""Единый клиент Bitrix24 REST API. Логи без домена портала и без токенов (mask)."""
import json
import logging
import time

import httpx

logger = logging.getLogger(__name__)

# Коды ошибок для установки (без утечки секретов)
BITRIX_ERR_AUTH_INVALID = "bitrix_auth_invalid"
BITRIX_ERR_METHOD_FORBIDDEN = "bitrix_method_forbidden"
BITRIX_ERR_RATE_LIMITED = "bitrix_rate_limited"
BITRIX_ERR_TIMEOUT = "bitrix_timeout"
BITRIX_ERR_BOT_NOT_REGISTERED = "bot_not_registered"
BITRIX_ERR_REST = "bitrix_rest_error"

# Единый источник истины для имени/кода бота (imbot.register)
BOT_NAME_DEFAULT = "Teachbase Ассистент"
BOT_CODE_DEFAULT = "teachbase_assistant"

# Канонический публичный префикс для Bitrix event URLs (host nginx: /v1 и/или /api/v1)
BITRIX_EVENT_API_PREFIX = "/v1"
OAUTH_TOKEN_URL = "https://oauth.bitrix.info/oauth/token/"


def _base_url(domain: str) -> str:
    d = domain.replace("https://", "").replace("http://", "").rstrip("/")
    return f"https://{d}"

def _oauth_token_urls(domain: str) -> list[str]:
    """OAuth endpoints to try (global first, then portal)."""
    urls = [OAUTH_TOKEN_URL]
    if domain:
        urls.append(f"{_base_url(domain)}/oauth/token/")
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u not in seen:
            out.append(u)
            seen.add(u)
    return out


def exchange_code(
    domain: str,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict | None:
    """Обмен code на access_token и refresh_token."""
    data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    try:
        for url in _oauth_token_urls(domain):
            with httpx.Client(timeout=30) as c:
                r = c.post(url, data=data)
                status_code = r.status_code
                try:
                    payload = r.json()
                except Exception:
                    payload = None
                if status_code >= 400:
                    continue
                if isinstance(payload, dict) and payload.get("access_token"):
                    return payload
        return None
    except Exception as e:
        logger.exception("Bitrix OAuth exchange failed: %s", e)
        return None


def refresh_token(
    domain: str,
    refresh_token_val: str,
    client_id: str,
    client_secret: str,
) -> tuple[dict | None, int | None, str]:
    """Обновить access_token по refresh_token."""
    data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token_val,
    }
    last_status = None
    last_desc = "no_response"
    try:
        for url in _oauth_token_urls(domain):
            with httpx.Client(timeout=30) as c:
                r = c.post(url, data=data)
                status_code = r.status_code
                last_status = status_code
                try:
                    payload = r.json()
                except Exception:
                    payload = None
                if status_code >= 400:
                    desc = ""
                    if isinstance(payload, dict):
                        desc = (payload.get("error_description") or payload.get("error") or "")
                    last_desc = desc or "http_error"
                    continue
                if isinstance(payload, dict):
                    if payload.get("access_token"):
                        return payload, status_code, ""
                    if payload.get("error_description") or payload.get("error"):
                        last_desc = (payload.get("error_description") or payload.get("error") or "")[:200]
                        continue
                last_desc = "invalid_response"
        return None, last_status, last_desc
    except Exception as e:
        logger.exception("Bitrix refresh token failed: %s", e)
        return None, None, str(e)[:200]


def _map_rest_error(status_code: int, body: dict | None) -> str:
    """Map HTTP/API error to stable code. No secrets in return."""
    if status_code == 401:
        return BITRIX_ERR_AUTH_INVALID
    if status_code == 403:
        return BITRIX_ERR_METHOD_FORBIDDEN
    if status_code == 429:
        return BITRIX_ERR_RATE_LIMITED
    if body and body.get("error"):
        desc = (body.get("error_description") or "").lower()
        if "bot" in desc or "imbot" in (body.get("error") or "").lower():
            return BITRIX_ERR_BOT_NOT_REGISTERED
    return BITRIX_ERR_REST


def _safe_error_description(body: dict | None) -> str:
    """Безопасное описание ошибки Bitrix (без секретов)."""
    if not body:
        return ""
    desc = (body.get("error_description") or body.get("error") or "")
    return (desc[:200] if isinstance(desc, str) else str(desc)[:200]).replace("***", "")


def rest_call_result(
    domain: str,
    access_token: str,
    method: str,
    params: dict | None = None,
    timeout_sec: int = 30,
    max_retries_429: int = 2,
) -> tuple[dict | None, str | None]:
    """
    REST вызов к Bitrix24. Возвращает (data, error_code).
    error_code: bitrix_auth_invalid, bitrix_method_forbidden, bitrix_rate_limited, bitrix_timeout, bot_not_registered, bitrix_rest_error.
    Retry только на 429 с backoff.
    """
    url = f"{_base_url(domain)}/rest/{method}"
    params = dict(params or {})
    params["auth"] = access_token
    last_body: dict | None = None
    for attempt in range(max_retries_429 + 1):
        try:
            with httpx.Client(timeout=timeout_sec) as c:
                r = c.post(url, data=params)
                try:
                    last_body = r.json()
                except Exception:
                    last_body = None
                if r.status_code == 429:
                    if attempt < max_retries_429:
                        retry_after = max(1, min(15, int(r.headers.get("Retry-After", 5))))
                        time.sleep(retry_after)
                        continue
                    return None, BITRIX_ERR_RATE_LIMITED
                if r.status_code >= 400:
                    return None, _map_rest_error(r.status_code, last_body)
                if last_body and last_body.get("error"):
                    logger.warning("Bitrix REST error: %s", _safe_error_description(last_body))
                    return None, _map_rest_error(r.status_code, last_body)
                return last_body or {}, None
        except httpx.TimeoutException:
            logger.warning("Bitrix REST timeout method=%s", method)
            return None, BITRIX_ERR_TIMEOUT
        except Exception as e:
            logger.exception("Bitrix REST failed: %s", e)
            return None, BITRIX_ERR_REST
    return None, BITRIX_ERR_RATE_LIMITED


def rest_call_result_detailed(
    domain: str,
    access_token: str,
    method: str,
    params: dict | None = None,
    timeout_sec: int = 30,
    max_retries_429: int = 2,
) -> tuple[dict | None, str | None, str, int]:
    """Как rest_call_result, но возвращает (data, error_code, error_description_safe, http_status)."""
    url = f"{_base_url(domain)}/rest/{method}"
    params = dict(params or {})
    params["auth"] = access_token
    last_body: dict | None = None
    last_status = 0
    for attempt in range(max_retries_429 + 1):
        try:
            with httpx.Client(timeout=timeout_sec) as c:
                r = c.post(url, data=params)
                last_status = r.status_code
                try:
                    last_body = r.json()
                except Exception:
                    last_body = None
                if r.status_code == 429:
                    if attempt < max_retries_429:
                        retry_after = max(1, min(15, int(r.headers.get("Retry-After", 5))))
                        time.sleep(retry_after)
                        continue
                    return None, BITRIX_ERR_RATE_LIMITED, _safe_error_description(last_body), last_status
                if r.status_code >= 400:
                    return None, _map_rest_error(r.status_code, last_body), _safe_error_description(last_body), last_status
                if last_body and last_body.get("error"):
                    return None, _map_rest_error(r.status_code, last_body), _safe_error_description(last_body), last_status
                return last_body or {}, None, "", last_status
        except httpx.TimeoutException:
            return None, BITRIX_ERR_TIMEOUT, "timeout", last_status or 0
        except Exception as e:
            logger.exception("Bitrix REST failed: %s", e)
            return None, BITRIX_ERR_REST, str(e)[:200], last_status or 0
    return None, BITRIX_ERR_RATE_LIMITED, _safe_error_description(last_body), last_status


def rest_call(
    domain: str,
    access_token: str,
    method: str,
    params: dict | None = None,
) -> dict | None:
    """REST вызов к Bitrix24 (legacy). При ошибке возвращает None."""
    data, _ = rest_call_result(domain, access_token, method, params)
    return data


def im_message_add(domain: str, access_token: str, dialog_id: str, message: str) -> bool:
    """Отправить сообщение (im.message.add)."""
    result = rest_call(
        domain,
        access_token,
        "im.message.add",
        {"DIALOG_ID": dialog_id, "MESSAGE": message},
    )
    return result is not None and "result" in result


def imbot_message_add(
    domain: str,
    access_token: str,
    bot_id: int,
    dialog_id: str,
    message: str,
) -> tuple[bool, str | None, str]:
    """Отправить сообщение от бота (imbot.message.add). Возвращает (ok, error_code, error_desc_safe)."""
    result, err, err_desc, status = rest_call_result_detailed(
        domain,
        access_token,
        "imbot.message.add",
        {"BOT_ID": bot_id, "DIALOG_ID": dialog_id, "MESSAGE": message},
        timeout_sec=15,
    )
    if err:
        return False, err, (err_desc or "")[:200]
    return (result is not None and "result" in result), None, ""


def imbot_chat_add(
    domain: str,
    access_token: str,
    bot_id: int,
    user_ids: list[int],
    title: str | None = None,
    message: str | None = None,
) -> tuple[int | None, str | None, str]:
    """
    Создать чат от имени бота (imbot.chat.add).
    USERS — список участников (один user_id для личного чата с ботом).
    Возвращает (chat_id, error_code, error_desc_safe). Success: chat_id из result.
    """
    if not user_ids:
        return None, "USERS_EMPTY", "No chat participants provided"
    # Bitrix REST form: массив как USERS[0]=id1, USERS[1]=id2
    params: dict[str, str | int] = {
        "BOT_ID": bot_id,
        "TYPE": "CHAT",
        "MESSAGE": (message or "").strip() or "Привет! Я Teachbase AI.",
    }
    if title:
        params["TITLE"] = title[:255]
    for i, uid in enumerate(user_ids):
        params[f"USERS[{i}]"] = uid
    result, err, err_desc, status = rest_call_result_detailed(
        domain,
        access_token,
        "imbot.chat.add",
        params,
        timeout_sec=15,
    )
    if err:
        return None, err, (err_desc or "")[:200]
    if result and result.get("error"):
        return None, result.get("error", "unknown"), (err_desc or _safe_error_description(result))[:200]
    # Success: numeric CHAT_ID (result или result.result)
    chat_id = result.get("result") if result else None
    if chat_id is not None:
        try:
            return int(chat_id), None, ""
        except (TypeError, ValueError):
            pass
    return None, "WRONG_REQUEST", (err_desc or "CHAT_ID not in response")[:200]


def _build_event_urls(events_base_url: str) -> list[str]:
    """Единый builder: каноника /v1/bitrix/events (без домена портала). Без двойных слешей."""
    base = (events_base_url or "").strip().rstrip("/")
    if not base or not base.startswith("http"):
        return []
    path = f"{BITRIX_EVENT_API_PREFIX}/bitrix/events".replace("//", "/")
    url = f"{base}{path}" if path.startswith("/") else f"{base}/{path}"
    return [url]


def _flatten_params_for_bitrix(params: dict) -> tuple[dict[str, str], list[str]]:
    """
    Разворачивает вложенные dict в bracket-ключи для application/x-www-form-urlencoded.
    Bitrix ожидает PROPERTIES[NAME]=..., PROPERTIES[COLOR]=...
    Возвращает (flat_dict, sent_keys).
    """
    flat: dict[str, str] = {}
    sent_keys: list[str] = []
    for k, v in params.items():
        if k == "auth":
            continue
        if isinstance(v, dict):
            for sub_k, sub_v in v.items():
                key = f"{k}[{sub_k}]"
                flat[key] = str(sub_v) if sub_v is not None else ""
                sent_keys.append(key)
        else:
            flat[k] = str(v) if v is not None else ""
            sent_keys.append(k)
    return flat, sent_keys


def _imbot_register_request_shape(
    flat_keys: list[str],
    events_url: str,
    public_base_url: str,
    top_level_name_enabled: bool,
) -> dict:
    """Форма запроса imbot.register для диагностики (без секретов)."""
    has_properties_name = "PROPERTIES[NAME]" in flat_keys or "PROPERTIES" in str(flat_keys)
    return {
        "has_NAME_top_level": top_level_name_enabled,
        "has_PROPERTIES_NAME": has_properties_name,
        "has_CODE": "CODE" in flat_keys,
        "has_EVENT_MESSAGE_ADD": "EVENT_MESSAGE_ADD" in flat_keys,
        "event_message_add_url": (events_url or "")[:200],
        "public_base_url": (public_base_url or "")[:200],
        "used_auth_type": "oauth_access_token",
        "api_prefix_used": BITRIX_EVENT_API_PREFIX,
        "content_type_sent": "application/x-www-form-urlencoded",
        "sent_keys": flat_keys,
    }


def imbot_register(
    domain: str,
    access_token: str,
    events_base_url: str | None = None,
    trace_id: str | None = None,
    portal_id: int | None = None,
) -> tuple[dict | None, str | None, str, list[str], int, int, dict]:
    """
    Регистрация бота (imbot.register).
    POST как application/x-www-form-urlencoded, PROPERTIES развёрнуты в PROPERTIES[NAME], etc.
    Без top-level NAME — только PROPERTIES[NAME] (как в официальных примерах Bitrix).
    Возвращает (result_dict, error_code, error_description_safe, event_urls_sent, http_status, time_ms, request_shape).
    """
    if events_base_url:
        base = events_base_url.rstrip("/")
    else:
        base = _base_url(domain)
    path = f"{BITRIX_EVENT_API_PREFIX}/bitrix/events".replace("//", "/")
    events_url = f"{base}{path}" if path.startswith("/") else f"{base}/{path}"
    event_urls_sent = _build_event_urls(events_base_url or base)
    if not event_urls_sent and base:
        event_urls_sent = [events_url]
    public_base = (events_base_url or base or "").strip()
    # Официальный формат Bitrix: PROPERTIES — вложенный объект, без top-level NAME
    params = {
        "CODE": BOT_CODE_DEFAULT,
        "TYPE": "B",
        "EVENT_MESSAGE_ADD": events_url,
        "EVENT_WELCOME_MESSAGE": events_url,
        "EVENT_BOT_DELETE": events_url,
        "PROPERTIES": {"NAME": BOT_NAME_DEFAULT, "LAST_NAME": "", "COLOR": "GREEN"},
    }
    flat_params, sent_keys = _flatten_params_for_bitrix(params)
    top_level_name_enabled = False
    request_shape = _imbot_register_request_shape(
        sent_keys, events_url, public_base, top_level_name_enabled
    )
    request_shape["api_prefix_used"] = BITRIX_EVENT_API_PREFIX
    request_shape["content_type_sent"] = "application/x-www-form-urlencoded"
    request_shape["sent_keys"] = sent_keys
    if trace_id is not None and portal_id is not None:
        t0 = time.perf_counter()
        data, err, err_desc, http_status = rest_call_result_detailed(
            domain, access_token, "imbot.register", flat_params, timeout_sec=15
        )
        time_ms = int((time.perf_counter() - t0) * 1000)
        raw_err = (data.get("error") if data else None) or (err or "")
        log_obj = {
            "type": "bitrix_rest",
            "action": "imbot.register",
            "trace_id": trace_id,
            "portal_id": portal_id,
            "http_status": http_status,
            "bitrix_error": raw_err,
            "bitrix_error_description": (err_desc or "")[:200],
            "bitrix_result_present": bool(data and (data.get("result") is not None or data.get("bot_id") is not None or data.get("BOT_ID") is not None)),
            "event_urls_sent": event_urls_sent,
            "time_ms": time_ms,
            "retry_count": 0,
            "request_shape": request_shape,
        }
        logger.info("bitrix_rest %s", json.dumps(log_obj, ensure_ascii=False))
        return data, err, err_desc or "", event_urls_sent, http_status, time_ms, request_shape
    data, err = rest_call_result(domain, access_token, "imbot.register", flat_params, timeout_sec=15)
    err_desc = ""
    if err:
        err_desc = err
    elif data and data.get("error"):
        err_desc = _safe_error_description(data)
    return data, err, err_desc, event_urls_sent, 0, 0, {}


def _normalize_bot_list_result(result: dict | None) -> list[dict]:
    """Bitrix result может быть list или dict с числовыми ключами (array of arrays)."""
    if not result:
        return []
    raw = result.get("result")
    if raw is None:
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        return [x for x in raw.values() if isinstance(x, dict)]
    return []


def imbot_bot_list(
    domain: str,
    access_token: str,
) -> tuple[list[dict], str | None]:
    """
    Список ботов портала (imbot.bot.list). Для проверки наличия бота.
    Возвращает (list ботов, error_code или None).
    """
    result, err = rest_call_result(
        domain, access_token, "imbot.bot.list", {}, timeout_sec=10
    )
    if err:
        return [], err
    if result and result.get("error"):
        return [], result.get("error", "unknown")
    return _normalize_bot_list_result(result), None


def imbot_bot_update(
    domain: str,
    access_token: str,
    bot_id: int,
    events_url: str,
    code: str = BOT_CODE_DEFAULT,
    name: str = BOT_NAME_DEFAULT,
) -> tuple[dict | None, str | None, str, int, int]:
    """
    imbot.update: задаёт EVENT_MESSAGE_ADD, EVENT_WELCOME_MESSAGE, EVENT_BOT_DELETE.
    Возвращает (data, error_code, error_desc_safe, http_status, latency_ms).
    """
    flat = {
        "BOT_ID": str(bot_id),
        "FIELDS[CODE]": code,
        "FIELDS[EVENT_MESSAGE_ADD]": events_url,
        "FIELDS[EVENT_WELCOME_MESSAGE]": events_url,
        "FIELDS[EVENT_BOT_DELETE]": events_url,
        "FIELDS[PROPERTIES][NAME]": name,
        "FIELDS[PROPERTIES][LAST_NAME]": "",
    }
    t0 = time.perf_counter()
    data, err, err_desc, status = rest_call_result_detailed(
        domain, access_token, "imbot.update", flat, timeout_sec=15
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)
    return data, err, err_desc or "", status or 0, latency_ms


def imbot_unregister(
    domain: str,
    access_token: str,
    bot_id: int,
) -> tuple[dict | None, str | None, str, int]:
    """
    imbot.unregister: удаление бота (официальный метод Bitrix24).
    Возвращает (data, error_code, error_desc_safe, http_status).
    """
    params = {"BOT_ID": str(bot_id)}
    data, err, err_desc, status = rest_call_result_detailed(
        domain, access_token, "imbot.unregister", params, timeout_sec=10
    )
    return data, err, err_desc or "", status or 0


def user_get(
    domain: str,
    access_token: str,
    start: int = 0,
    limit: int = 50,
) -> tuple[list[dict], str | None]:
    """
    Список пользователей (user.get). Требует scope user.
    Возвращает (list пользователей, error_code или None).
    """
    result = rest_call(
        domain,
        access_token,
        "user.get",
        {"start": start, "filter": {"ACTIVE": True}},
    )
    if result is None:
        return [], "rest_error"
    if result.get("error"):
        desc = (result.get("error_description") or "").lower()
        if "insufficient" in desc or "scope" in desc or "access" in desc:
            return [], "missing_scope_user"
        return [], result.get("error", "unknown")
    items = result.get("result") or []
    return items[:limit], None


def user_current(
    domain: str,
    access_token: str,
) -> tuple[int | None, str | None]:
    """
    Текущий пользователь (user.current). Возвращает (user_id, error_code).
    """
    result = rest_call(domain, access_token, "user.current", {})
    if result is None:
        return None, "rest_error"
    if result.get("error"):
        return None, result.get("error", "unknown")
    data = result.get("result") or {}
    uid = data.get("ID") or data.get("id")
    try:
        return int(uid), None
    except (TypeError, ValueError):
        return None, "invalid_user_id"
