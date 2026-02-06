"""Безопасный парсер входящих Bitrix запросов: query + form + json."""
import json
import logging
from typing import Any

from starlette.requests import Request

logger = logging.getLogger(__name__)


def _assign_bracketed(out: dict[str, Any], key: str, value: Any) -> None:
    if "[" not in key or "]" not in key:
        out[key] = value
        return
    parts: list[str] = []
    buf = ""
    i = 0
    while i < len(key):
        ch = key[i]
        if ch == "[":
            if buf:
                parts.append(buf)
                buf = ""
            j = key.find("]", i + 1)
            if j == -1:
                break
            parts.append(key[i + 1:j])
            i = j + 1
            continue
        buf += ch
        i += 1
    if buf:
        parts.append(buf)
    if not parts:
        return
    cur = out
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


async def parse_bitrix_body(request: Request) -> dict[str, Any]:
    """
    Собирает merged_params из query, form, json.
    Приоритет: query < form < json.
    Никогда не падает с JSONDecodeError.
    """
    merged: dict[str, Any] = {}

    # 1. Query params
    merged.update(dict(request.query_params))

    # 2. Form (application/x-www-form-urlencoded, multipart)
    ct = (request.headers.get("content-type") or "").lower()
    if "application/x-www-form-urlencoded" in ct or "multipart/form-data" in ct:
        try:
            form = await request.form()
            for k, v in form.items():
                val: Any = v
                if isinstance(v, str) and v.strip().startswith(("{", "[")):
                    try:
                        val = json.loads(v)
                    except json.JSONDecodeError:
                        val = v
                _assign_bracketed(merged, k, val)
        except Exception as e:
            logger.warning("bitrix parse form error: %s", e)

    # 3. JSON (только если content-type application/json)
    elif "application/json" in ct:
        try:
            body = await request.body()
            if body:
                merged.update(json.loads(body))
        except json.JSONDecodeError as e:
            logger.warning("bitrix parse json error: %s", e)
        except Exception as e:
            logger.warning("bitrix parse body error: %s", e)

    return merged
