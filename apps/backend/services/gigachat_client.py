"""GigaChat API client (admin only)."""
from __future__ import annotations

from typing import Any
from uuid import uuid4
import time
import os
import json
import logging

import httpx

logger = logging.getLogger(__name__)

DEFAULT_OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
DEFAULT_API_BASE = "https://gigachat.devices.sberbank.ru/api/v1"
DEFAULT_RETRIES = 2
DEFAULT_BACKOFF = 0.8


def _httpx_verify_setting() -> bool | str:
    """
    SSL verify control:
    - GIGACHAT_CA_BUNDLE=/path/to/ca.pem -> use custom CA bundle
    - GIGACHAT_INSECURE_SSL=1 -> disable verify (not recommended)
    """
    ca_bundle = (os.getenv("GIGACHAT_CA_BUNDLE") or "").strip()
    if ca_bundle:
        return ca_bundle
    insecure = (os.getenv("GIGACHAT_INSECURE_SSL") or "").strip().lower()
    if insecure in ("1", "true", "yes", "on"):
        return False
    return True


def _mask_key(key: str) -> str:
    k = (key or "").strip()
    if len(k) <= 14:
        return "***"
    return f"{k[:7]}...{k[-7:]}"


def _normalize_err(err: str) -> str:
    if not err:
        return "unknown_error"
    low = err.lower()
    if "connection reset by peer" in low or "errno 104" in low:
        return "connection_reset"
    if "certificate verify failed" in low:
        return "ssl_verify_failed"
    if "timeout" in low:
        return "timeout"
    return err[:200]


def _request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: dict | None = None,
    json_body: dict | None = None,
    timeout: int = 15,
    retries: int = DEFAULT_RETRIES,
) -> tuple[httpx.Response | None, dict, str | None]:
    verify = _httpx_verify_setting()
    last_err = None
    for attempt in range(retries + 1):
        try:
            r = httpx.request(
                method,
                url,
                headers=headers,
                data=data,
                json=json_body,
                timeout=timeout,
                verify=verify,
            )
            payload = r.json() if r.content else {}
            return r, payload, None
        except (httpx.RequestError, OSError) as e:
            last_err = _normalize_err(str(e))
            if attempt < retries:
                time.sleep(DEFAULT_BACKOFF * (attempt + 1))
                continue
            return None, {}, last_err
    return None, {}, last_err


def request_access_token_detailed(
    auth_key: str,
    scope: str,
) -> tuple[str | None, int | None, str | None, int]:
    if not auth_key:
        return None, None, "missing_auth_key", 0
    if not scope:
        return None, None, "missing_scope", 0
    auth_header = auth_key.strip()
    # Пользователь иногда вставляет целиком "Authorization: Basic <key>"
    if auth_header.lower().startswith("authorization:"):
        auth_header = auth_header.split(":", 1)[1].strip()
    # Нормализуем: убираем префиксы и пробелы/переводы строк
    lowered = auth_header.lower()
    if lowered.startswith("basic "):
        auth_header = auth_header[6:]
    elif lowered.startswith("bearer "):
        auth_header = auth_header[7:]
    auth_header = "".join(auth_header.split())
    # По документации GigaChat Authorization key передаётся как Basic <key>
    auth_header = f"Basic {auth_header}"
    headers = {
        "Authorization": auth_header,
        "RqUID": str(uuid4()),
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    data = {"scope": scope}
    key_info = {
        "auth_key_masked": _mask_key(auth_header.replace("Basic ", "")),
        "auth_key_len": len(auth_header.replace("Basic ", "")),
        "scope": scope,
        "url": DEFAULT_OAUTH_URL,
    }
    r, payload, err = _request_json(
        "POST",
        DEFAULT_OAUTH_URL,
        headers=headers,
        data=data,
        timeout=15,
    )
    if err:
        logger.warning("gigachat_token_request_error %s", json.dumps({**key_info, "error": err[:120]}, ensure_ascii=False))
        return None, None, err[:200], 0
    if r.status_code >= 400:
        err = (payload.get("error_description") or payload.get("error") or str(r.status_code))
        if str(r.status_code) == "401":
            err = "401 unauthorized: проверьте Authorization key (это не client_id)"
        logger.warning("gigachat_token_request_failed %s", json.dumps({**key_info, "status": r.status_code, "error": err[:120]}, ensure_ascii=False))
        return None, None, err[:200], r.status_code
    token = payload.get("access_token")
    expires_at = payload.get("expires_at")
    if token and not expires_at:
        expires_at = int(time.time()) + 1800
    if isinstance(expires_at, (int, float)) and expires_at > 10**11:
        # API may return milliseconds; normalize to seconds
        expires_at = int(expires_at / 1000)
    logger.info("gigachat_token_request_ok %s", json.dumps({**key_info, "status": r.status_code}, ensure_ascii=False))
    return token, int(expires_at) if expires_at else None, None, r.status_code


def request_access_token(auth_key: str, scope: str) -> tuple[str | None, int | None, str | None]:
    token, expires_at, err, _status = request_access_token_detailed(auth_key, scope)
    return token, expires_at, err


def list_models(api_base: str, access_token: str) -> tuple[list[dict], str | None]:
    if not access_token:
        return [], "missing_access_token"
    base = (api_base or DEFAULT_API_BASE).rstrip("/")
    url = f"{base}/models"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "RqUID": str(uuid4()),
    }
    r, payload, err = _request_json("GET", url, headers=headers, timeout=15)
    if err:
        return [], err[:200]
    if r.status_code >= 400:
        err = (payload.get("error_description") or payload.get("error") or str(r.status_code))
        return [], err[:200]
    items = payload.get("data") or payload.get("result") or payload.get("models") or []
    if isinstance(items, list):
        return items, None
    return [], None


def create_embeddings(
    api_base: str,
    access_token: str,
    model: str,
    texts: list[str],
) -> tuple[list[list[float]], str | None, dict | None]:
    if not access_token:
        return [], "missing_access_token", None
    if not model:
        return [], "missing_model", None
    base = (api_base or DEFAULT_API_BASE).rstrip("/")
    url = f"{base}/embeddings"
    logger.info("gigachat_embeddings_request %s", json.dumps({"model": model, "batch": len(texts)}, ensure_ascii=False))
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "RqUID": str(uuid4()),
    }
    payload = {"model": model, "input": texts}
    r, data, err = _request_json("POST", url, headers=headers, json_body=payload, timeout=30)
    if err:
        return [], err[:200], None
    if r.status_code >= 400:
        err = (data.get("error_description") or data.get("error") or str(r.status_code))
        return [], err[:200], None
    items = data.get("data") or data.get("embeddings") or []
    vectors: list[list[float]] = []
    if isinstance(items, list):
        for it in items:
            vec = it.get("embedding") if isinstance(it, dict) else None
            if isinstance(vec, list):
                vectors.append(vec)
    usage = data.get("usage") if isinstance(data, dict) else None
    return vectors, None, usage


def chat_complete(
    api_base: str,
    access_token: str,
    model: str,
    messages: list[dict[str, Any]],
    temperature: float = 0.2,
    max_tokens: int = 800,
    top_p: float | None = None,
    presence_penalty: float | None = None,
    frequency_penalty: float | None = None,
) -> tuple[str | None, str | None, dict | None]:
    if not access_token:
        return None, "missing_access_token", None
    if not model:
        return None, "missing_model", None
    base = (api_base or DEFAULT_API_BASE).rstrip("/")
    url = f"{base}/chat/completions"
    logger.info("gigachat_chat_request %s", json.dumps({"model": model, "messages": len(messages)}, ensure_ascii=False))
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "RqUID": str(uuid4()),
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if top_p is not None:
        payload["top_p"] = top_p
    if presence_penalty is not None:
        payload["presence_penalty"] = presence_penalty
    if frequency_penalty is not None:
        payload["frequency_penalty"] = frequency_penalty
    r, data, err = _request_json("POST", url, headers=headers, json_body=payload, timeout=60)
    if err:
        return None, err[:200], None
    if r.status_code >= 400:
        err = (data.get("error_description") or data.get("error") or str(r.status_code))
        return None, err[:200], None
    choices = data.get("choices") or []
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message") or {}
        content = msg.get("content")
        if content:
            return str(content), None, data.get("usage")
    return None, "empty_response", data.get("usage") if isinstance(data, dict) else None
