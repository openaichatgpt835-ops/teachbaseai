"""Middleware: логирование Bitrix запросов."""
import json
import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from apps.backend.database import get_session_factory
from apps.backend.middleware.trace_id import ensure_trace_id
from apps.backend.services.bitrix_logging import log_inbound

logger = logging.getLogger("uvicorn.error")


_MAX_JSON_FIELD_CHARS = 16_000


def _mask_payload(value):
    """Mask sensitive fields recursively for trace-safe diagnostics."""
    secret_keys = {
        "access_token",
        "refresh_token",
        "token",
        "auth",
        "authorization",
        "password",
        "client_secret",
        "secret",
        "webhook_secret",
    }
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            kl = str(k).lower()
            if kl in secret_keys or "token" in kl or "secret" in kl or "password" in kl or "authorization" in kl:
                out[k] = "[MASKED]" if v else None
            else:
                out[k] = _mask_payload(v)
        return out
    if isinstance(value, list):
        return [_mask_payload(v) for v in value]
    return value


def _truncate_payload(value):
    """Bound payload size to keep DB rows compact."""
    try:
        raw = json.dumps(value, ensure_ascii=False)
    except Exception:
        return value
    if len(raw) <= _MAX_JSON_FIELD_CHARS:
        return value
    clipped = raw[:_MAX_JSON_FIELD_CHARS]
    return {"_truncated": True, "preview": clipped}


class BitrixLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not (request.url.path.startswith("/v1/bitrix") or request.url.path.startswith("/api/v1/bitrix")):
            return await call_next(request)
        trace_id = ensure_trace_id(request.scope)
        request.state.trace_id = trace_id
        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = int((time.perf_counter() - start) * 1000)
        query_keys = list(request.query_params.keys())
        body_keys = []
        request_json = None
        response_json = None
        headers_min = {
            "accept": (request.headers.get("accept", "") or "")[:256],
            "content_type": (request.headers.get("content-type", "") or "")[:128],
            "x_requested_with": (request.headers.get("x-requested-with", "") or "")[:64],
        }
        try:
            ct = (request.headers.get("content-type", "") or "").lower()
            if "application/json" in ct:
                body_bytes = await request.body()
                if body_bytes:
                    parsed = json.loads(body_bytes.decode("utf-8", errors="replace"))
                    request_json = _truncate_payload(_mask_payload(parsed))
        except Exception:
            request_json = {"_parse_error": True}
        accept = request.headers.get("accept", "")
        sec_fetch_dest = request.headers.get("sec-fetch-dest", "")
        sec_fetch_mode = request.headers.get("sec-fetch-mode", "")
        x_requested_with = request.headers.get("x-requested-with", "")
        user_agent = request.headers.get("user-agent", "")
        response_content_type = response.headers.get("content-type", "") if hasattr(response, "headers") else ""
        response_length = None
        response_is_json = None
        try:
            if hasattr(response, "body") and response.body is not None:
                body = response.body
                if isinstance(body, bytes):
                    response_length = len(body)
                    prefix = body[:1].decode(errors="ignore") if body else ""
                    response_is_json = prefix in ("{", "[")
                    if response_is_json:
                        try:
                            parsed_resp = json.loads(body.decode("utf-8", errors="replace"))
                            response_json = _truncate_payload(_mask_payload(parsed_resp))
                        except Exception:
                            response_json = {"_parse_error": True}
                else:
                    text = str(body)
                    response_length = len(text.encode("utf-8"))
                    response_is_json = text.lstrip().startswith("{") or text.lstrip().startswith("[")
                    if response_is_json:
                        try:
                            parsed_resp = json.loads(text)
                            response_json = _truncate_payload(_mask_payload(parsed_resp))
                        except Exception:
                            response_json = {"_parse_error": True}
            else:
                clen = response.headers.get("content-length", "") if hasattr(response, "headers") else ""
                response_length = int(clen) if str(clen).isdigit() else None
                response_is_json = (response_content_type or "").startswith("application/json")
        except Exception:
            pass
        try:
            factory = get_session_factory()
            with factory() as db:
                log_inbound(
                    db,
                    trace_id=trace_id,
                    method=request.method,
                    path=request.url.path,
                    query_keys=query_keys,
                    body_keys=body_keys,
                    status_code=response.status_code,
                    latency_ms=latency_ms,
                    portal_id=None,
                    accept=accept,
                    sec_fetch_dest=sec_fetch_dest,
                    sec_fetch_mode=sec_fetch_mode,
                    user_agent=user_agent,
                    response_content_type=response_content_type,
                    response_length=response_length,
                    response_is_json=response_is_json,
                    request_json=request_json,
                    response_json=response_json,
                    headers_min=headers_min,
                )
        except Exception:
            pass
        try:
            probe = {
                "type": "bitrix_iframe_probe",
                "trace_id": trace_id,
                "method": request.method,
                "path": request.url.path,
                "query_keys": query_keys,
                "status": response.status_code,
                "response_content_type": response_content_type,
                "response_length": response_length,
                "accept": (accept or "")[:256],
                "sec_fetch_dest": (sec_fetch_dest or "")[:64],
                "sec_fetch_mode": (sec_fetch_mode or "")[:64],
                "x_requested_with": (x_requested_with or "")[:64],
                "user_agent": (user_agent or "")[:128],
            }
            logger.info(json.dumps(probe, ensure_ascii=False))
        except Exception:
            pass
        return response
