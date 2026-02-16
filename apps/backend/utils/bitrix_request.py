"""Безопасный парсер входящих Bitrix запросов: query + form + json."""
import json
import logging
from urllib.parse import parse_qs
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

    # 2. Body parse (handles missing/incorrect content-type)
    ct = (request.headers.get("content-type") or "").lower()
    is_json = "application/json" in ct
    body = b""
    try:
        body = await request.body()
    except Exception as e:
        logger.warning("bitrix read body error: %s", e)
        body = b""

    if body:
        body_str = ""
        try:
            body_str = body.decode("utf-8", errors="ignore")
        except Exception:
            body_str = ""

        # Try JSON first if content-type says JSON or body looks like JSON
        if is_json or body_str.lstrip().startswith(("{", "[")):
            try:
                merged.update(json.loads(body_str))
            except json.JSONDecodeError as e:
                logger.warning("bitrix parse json error: %s", e)
            except Exception as e:
                logger.warning("bitrix parse body error: %s", e)
        else:
            # Fallback: parse as urlencoded (even if content-type missing)
            try:
                qs = parse_qs(body_str, keep_blank_values=True)
                for k, vals in qs.items():
                    if not vals:
                        _assign_bracketed(merged, k, "")
                        continue
                    for v in vals:
                        val: Any = v
                        if isinstance(v, str) and v.strip().startswith(("{", "[")):
                            try:
                                val = json.loads(v)
                            except json.JSONDecodeError:
                                val = v
                        _assign_bracketed(merged, k, val)
            except Exception as e:
                logger.warning("bitrix parse urlencoded error: %s", e)

    return merged
