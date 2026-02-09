"""Telegram Bot API client."""
from __future__ import annotations

import httpx


def _api_url(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def telegram_get_me(token: str) -> tuple[dict | None, str | None]:
    try:
        r = httpx.get(_api_url(token, "getMe"), timeout=15)
        data = r.json()
        if not data.get("ok"):
            return None, data.get("description") or "error"
        return data.get("result"), None
    except Exception as e:
        return None, str(e)[:200]


def telegram_set_webhook(token: str, url: str, secret_token: str) -> tuple[bool, str | None]:
    payload = {"url": url, "secret_token": secret_token}
    try:
        r = httpx.post(_api_url(token, "setWebhook"), json=payload, timeout=20)
        data = r.json()
        if not data.get("ok"):
            return False, data.get("description") or "error"
        return True, None
    except Exception as e:
        return False, str(e)[:200]


def telegram_send_message(token: str, chat_id: str | int, text: str) -> tuple[bool, str | None]:
    payload = {"chat_id": chat_id, "text": text}
    try:
        r = httpx.post(_api_url(token, "sendMessage"), json=payload, timeout=20)
        data = r.json()
        if not data.get("ok"):
            return False, data.get("description") or "error"
        return True, None
    except Exception as e:
        return False, str(e)[:200]


def telegram_get_file(token: str, file_id: str) -> tuple[dict | None, str | None]:
    payload = {"file_id": file_id}
    try:
        r = httpx.post(_api_url(token, "getFile"), json=payload, timeout=20)
        data = r.json()
        if not data.get("ok"):
            return None, data.get("description") or "error"
        return data.get("result"), None
    except Exception as e:
        return None, str(e)[:200]


def telegram_download_file(token: str, file_path: str, dst_path: str) -> tuple[bool, str | None]:
    url = f"https://api.telegram.org/file/bot{token}/{file_path}"
    try:
        with httpx.stream("GET", url, timeout=60) as r:
            if r.status_code >= 400:
                return False, f"http_{r.status_code}"
            with open(dst_path, "wb") as f:
                for chunk in r.iter_bytes():
                    if chunk:
                        f.write(chunk)
        return True, None
    except Exception as e:
        return False, str(e)[:200]
