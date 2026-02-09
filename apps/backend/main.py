"""Точка входа FastAPI."""
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from apps.backend.middleware.bitrix_log import BitrixLogMiddleware
from apps.backend.middleware.bitrix_inbound_events import BitrixInboundEventsMiddleware
from apps.backend.routers import health, admin_auth, admin_portals
from apps.backend.routers import admin_dialogs, admin_events, admin_outbox
from apps.backend.routers import admin_system, admin_logs, admin_traces, admin_debug
from apps.backend.routers import admin_settings, admin_inbound_events, admin_billing, admin_registrations
from apps.backend.routers import bitrix, portal, debug, admin_kb, telegram, web_auth

logger = logging.getLogger(__name__)


def _is_xhr_request(request: Request) -> bool:
    """XHR/fetch: X-Requested-With: XMLHttpRequest OR Accept contains application/json, Sec-Fetch-Mode != navigate."""
    h = request.headers
    if (h.get("X-Requested-With") or "").strip() == "XMLHttpRequest":
        return True
    accept = (h.get("Accept") or "").lower()
    if "application/json" in accept:
        mode = (h.get("Sec-Fetch-Mode") or "").strip().lower()
        if mode and mode != "navigate":
            return True
    return False


def _is_bitrix_xhr_path(path: str) -> bool:
    return path.startswith("/v1/bitrix/") or path.startswith("/api/v1/bitrix/")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # shutdown


app = FastAPI(
    title="Teachbase AI",
    description="Bitrix24 Marketplace multi-portal chat",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(BitrixInboundEventsMiddleware)
app.add_middleware(BitrixLogMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["System"])
app.include_router(admin_auth.router, prefix="/v1/admin/auth", tags=["Admin Auth"])
app.include_router(admin_portals.router, prefix="/v1/admin/portals", tags=["Admin Portals"])
app.include_router(admin_dialogs.router, prefix="/v1/admin/dialogs", tags=["Admin Dialogs"])
app.include_router(admin_events.router, prefix="/v1/admin/events", tags=["Admin Events"])
app.include_router(admin_outbox.router, prefix="/v1/admin/outbox", tags=["Admin Outbox"])
app.include_router(admin_system.router, prefix="/v1/admin/system", tags=["Admin System"])
app.include_router(admin_logs.router, prefix="/v1/admin/logs", tags=["Admin Logs"])
app.include_router(admin_traces.router, prefix="/v1/admin/traces", tags=["Admin Traces"])
app.include_router(admin_debug.router, prefix="/v1/admin/debug", tags=["Admin Debug"])
app.include_router(admin_settings.router, prefix="/v1/admin/settings", tags=["Admin Settings"])
app.include_router(admin_inbound_events.router, prefix="/v1/admin", tags=["Admin Inbound Events"])
app.include_router(admin_kb.router, prefix="/v1/admin/kb", tags=["Admin KB"])
app.include_router(admin_billing.router, prefix="/v1/admin/billing", tags=["Admin Billing"])
app.include_router(admin_registrations.router, prefix="/v1/admin", tags=["Admin Registrations"])
app.include_router(bitrix.router, prefix="/v1/bitrix", tags=["Bitrix"])
app.include_router(telegram.router, prefix="/v1/telegram", tags=["Telegram"])
app.include_router(portal.router, prefix="/v1/portal", tags=["Portal"])
app.include_router(web_auth.router, prefix="/v1/web", tags=["Web"])
app.include_router(debug.router, prefix="/v1/debug", tags=["Debug"])


def _xhr_error_payload(trace_id: str, error: str, message: str, detail: str | None = None) -> dict:
    out = {"error": error, "trace_id": trace_id, "message": message}
    if detail:
        out["detail"] = detail
    return out


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """For XHR to /v1/bitrix/* always return JSON with trace_id."""
    path = request.url.path
    if _is_bitrix_xhr_path(path) and _is_xhr_request(request):
        trace_id = getattr(request.state, "trace_id", None) or str(uuid.uuid4())[:16]
        payload = _xhr_error_payload(
            trace_id,
            "http_error",
            exc.detail if isinstance(exc.detail, str) else "Ошибка запроса",
            str(exc.detail) if exc.detail and not isinstance(exc.detail, str) else None,
        )
        resp = JSONResponse(content=payload, status_code=exc.status_code)
        resp.headers["X-Trace-Id"] = trace_id
        return resp
    detail = exc.detail
    if not isinstance(detail, str):
        detail = str(detail) if detail else "Ошибка"
    return JSONResponse(content={"detail": detail}, status_code=exc.status_code)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """For XHR to /v1/bitrix/* never return HTML — always JSON with trace_id."""
    path = request.url.path
    trace_id = getattr(request.state, "trace_id", None) or str(uuid.uuid4())[:16]
    logger.exception("Unhandled exception trace_id=%s path=%s", trace_id, path)
    if _is_bitrix_xhr_path(path) and _is_xhr_request(request):
        detail_safe = str(exc)[:200].replace("'", "")  # safe, no secrets in repr
        payload = _xhr_error_payload(
            trace_id,
            "internal_error",
            "Внутренняя ошибка сервера",
            detail_safe,
        )
        resp = JSONResponse(content=payload, status_code=500)
        resp.headers["X-Trace-Id"] = trace_id
        return resp
    raise exc
