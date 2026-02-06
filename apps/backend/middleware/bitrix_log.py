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
                else:
                    text = str(body)
                    response_length = len(text.encode("utf-8"))
                    response_is_json = text.lstrip().startswith("{") or text.lstrip().startswith("[")
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
