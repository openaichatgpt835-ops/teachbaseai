"""Middleware: blackbox logging for POST /v1/bitrix/events only. ASGI: reads body once, logs, replays body to handler."""
import logging

from apps.backend import database
from apps.backend.middleware.trace_id import ensure_trace_id
from apps.backend.services.bitrix_inbound_log import (
    build_inbound_event_record,
    run_retention,
)
from apps.backend.services.inbound_settings import get_inbound_settings

logger = logging.getLogger("uvicorn.error")

EVENTS_PATH = "/v1/bitrix/events"
EVENTS_PATH_ALT = "/api/v1/bitrix/events"


def _is_events_post(scope: dict) -> bool:
    if scope.get("type") != "http":
        return False
    if (scope.get("method") or "").upper() != "POST":
        return False
    path = (scope.get("path") or "").rstrip("/")
    return path == EVENTS_PATH.rstrip("/") or path == EVENTS_PATH_ALT.rstrip("/")


def _scope_headers_to_dict(scope: dict) -> dict:
    out = {}
    for raw_k, raw_v in scope.get("headers") or []:
        try:
            k = raw_k.decode("utf-8", errors="replace").lower()
            v = raw_v.decode("utf-8", errors="replace")
            out[k] = v
        except Exception:
            pass
    return out


def _scope_query_string(scope: dict) -> str | None:
    qs = scope.get("query_string")
    if not qs:
        return None
    return qs.decode("utf-8", errors="replace")


class BitrixInboundEventsMiddleware:
    """
    ASGI middleware: only for POST /v1/bitrix/events.
    Reads body from receive() once, saves to bitrix_inbound_events, then passes
    a new receive() that replays the cached body so the route gets the same body.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope: dict, receive, send):
        if not _is_events_post(scope):
            await self.app(scope, receive, send)
            return

        trace_id = ensure_trace_id(scope)
        body_chunks = []
        more_body = True
        try:
            while more_body:
                message = await receive()
                if message.get("type") == "http.disconnect":
                    break
                if message.get("type") == "http.request":
                    body_chunks.append(message.get("body") or b"")
                    more_body = message.get("more_body", False)
                else:
                    more_body = False
        except Exception as e:
            logger.warning("bitrix_inbound_events read body failed: %s", e)
            await self.app(scope, receive, send)
            return

        body_bytes = b"".join(body_chunks)

        try:
            factory = database.get_session_factory()
            with factory() as db:
                settings = get_inbound_settings(db)
                if not settings.get("enabled", True):
                    pass
                else:
                    headers_dict = _scope_headers_to_dict(scope)
                    query_domain = None
                    qs = _scope_query_string(scope)
                    if qs:
                        from urllib.parse import parse_qs
                        params = parse_qs(qs)
                        query_domain = (params.get("DOMAIN") or params.get("domain") or [None])[0]
                    build_inbound_event_record(
                        db=db,
                        trace_id=trace_id,
                        method=(scope.get("method") or "POST"),
                        path=(scope.get("path") or "/v1/bitrix/events"),
                        query_string=qs,
                        content_type=headers_dict.get("content-type"),
                        request_headers=headers_dict,
                        body_bytes=body_bytes,
                        remote_ip=scope.get("client", (None, None))[0] if scope.get("client") else None,
                        query_domain=query_domain,
                        settings=settings,
                    )
                    if settings.get("auto_prune_on_write", True):
                        run_retention(db, settings)
        except Exception as e:
            logger.warning("INBOUND_LOG_FAILED trace_id=%s error=%s", trace_id, e)

        sent = []

        async def replay_receive():
            if not sent:
                sent.append(True)
                return {"type": "http.request", "body": body_bytes, "more_body": False}
            return {"type": "http.disconnect"}

        await self.app(scope, replay_receive, send)
