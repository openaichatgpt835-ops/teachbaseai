"""Bitrix OAuth, install, handler, events."""
import json
import logging
import os
import uuid
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Request, Depends, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse, PlainTextResponse

from pydantic import BaseModel

from sqlalchemy.orm import Session
from sqlalchemy import select, delete, func

from apps.backend.deps import get_db
from apps.backend.config import get_settings
from apps.backend.models.portal import Portal, PortalUsersAccess
from apps.backend.models.dialog import Dialog, Message
from apps.backend.models.bitrix_inbound_event import BitrixInboundEvent
from apps.backend.models.kb import KBFile, KBJob, KBSource, KBChunk, KBEmbedding
from apps.backend.auth import create_portal_token_with_user, require_portal_access, decode_token
from apps.backend.clients.bitrix import exchange_code, user_current, user_get
from apps.backend.services.bitrix_events import process_imbot_message
from apps.backend.services.portal_tokens import save_tokens, get_valid_access_token, BitrixAuthError
from apps.backend.services.token_crypto import encrypt_token
from apps.backend.services.kb_storage import ensure_portal_dir, save_upload
from apps.backend.services.kb_settings import get_portal_kb_settings, set_portal_kb_settings
from apps.backend.services.kb_sources import create_url_source
from apps.backend.services.billing import get_portal_usage_summary
from apps.backend.services.gigachat_client import list_models, DEFAULT_API_BASE
from apps.backend.services.kb_settings import get_effective_gigachat_settings, get_valid_gigachat_access_token
from apps.backend.services.gigachat_client import chat_complete
from apps.backend.models.topic_summary import PortalTopicSummary
from apps.backend.services.portal_tokens import get_access_token
from apps.backend.services.bot_provisioning import ensure_bot_registered
from apps.backend.services.finalize_install import step_provision_chats, _now_trace_id
from apps.backend.services.finalize_install import finalize_install, step_provision_chats
from apps.backend.services.bot_provisioning import ensure_bot_registered
from apps.backend.clients.bitrix import imbot_bot_list, BOT_CODE_DEFAULT
from apps.backend.utils.bitrix_request import parse_bitrix_body

router = APIRouter()

_install_html: str | None = None
_handler_html: str | None = None
_app_html: str | None = None


def _html_ui_response(html: str) -> HTMLResponse:
    resp = HTMLResponse(html)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    resp.headers["X-Teachbase-UI"] = "1"
    return resp


def _load_install_html() -> str:
    global _install_html
    if _install_html is None:
        p = Path(__file__).resolve().parent.parent / "templates" / "install.html"
        _install_html = p.read_text(encoding="utf-8")
    return _install_html


def _load_handler_html() -> str:
    global _handler_html
    if _handler_html is None:
        p = Path(__file__).resolve().parent.parent / "templates" / "handler.html"
        _handler_html = p.read_text(encoding="utf-8")
    return _handler_html


def _load_app_html() -> str:
    global _app_html
    if _app_html is None:
        p = Path(__file__).resolve().parent.parent / "templates" / "app.html"
        _app_html = p.read_text(encoding="utf-8")
    return _app_html


def _domain_clean(domain: str) -> str:
    return domain.replace("https://", "").replace("http://", "").rstrip("/").split("/")[0]


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "") or ""


def _portal_user_id_from_token(request: Request) -> int | None:
    auth = request.headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    payload = decode_token(token)
    if not payload:
        return None
    uid = payload.get("uid")
    try:
        return int(uid) if uid is not None else None
    except (TypeError, ValueError):
        return None


def _is_document_navigation(request: Request) -> bool:
    h = request.headers
    dest = (h.get("Sec-Fetch-Dest") or "").strip().lower()
    if dest in ("document", "iframe", "embed"):
        return True
    mode = (h.get("Sec-Fetch-Mode") or "").strip().lower()
    if mode == "navigate":
        return True
    accept = (h.get("Accept") or "").lower()
    if "text/html" in accept or "application/xhtml+xml" in accept:
        return True
    return False


def _is_json_api_request(request: Request) -> bool:
    h = request.headers
    if _is_document_navigation(request):
        return False
    if h.get("X-Requested-With") == "XMLHttpRequest":
        return True
    accept = (h.get("Accept") or "").lower()
    mode = (h.get("Sec-Fetch-Mode") or "").strip().lower()
    if "application/json" in accept and mode in ("cors", "same-origin", "no-cors"):
        return True
    return False


def _log_bitrix_install_xhr(
    trace_id: str,
    portal_id: int | None,
    step: str,
    path: str,
    http_status: int,
    bitrix_method: str | None = None,
    err_code: str | None = None,
    safe_err: str | None = None,
) -> None:
    """Structured log for install XHR. No domain, no tokens."""
    log_obj = {
        "type": "bitrix_install_xhr",
        "trace_id": trace_id,
        "portal_id": portal_id,
        "step": step,
        "path": path,
        "http_status": http_status,
    }
    if bitrix_method:
        log_obj["bitrix_method"] = bitrix_method
    if err_code:
        log_obj["err_code"] = err_code
    if safe_err:
        log_obj["safe_err"] = safe_err[:200]
    logger.info("bitrix_install_xhr %s", json.dumps(log_obj, ensure_ascii=False))


def _parse_install_auth(merged: dict) -> tuple[str | None, str | None, str | None, str, str | None, str | None, str | None, int | None]:
    auth = merged.get("auth", merged)
    if isinstance(auth, str):
        try:
            auth = json.loads(auth) if auth else {}
        except Exception:
            auth = {}
    if not isinstance(auth, dict):
        auth = {}
    access_token = (
        merged.get("AUTH_ID")
        or auth.get("access_token")
        or auth.get("ACCESS_TOKEN")
    )
    refresh_token = (
        merged.get("REFRESH_ID")
        or auth.get("refresh_token")
        or auth.get("REFRESH_TOKEN")
    )
    domain = merged.get("DOMAIN") or auth.get("domain") or auth.get("DOMAIN")
    member_id = str(merged.get("MEMBER_ID") or auth.get("member_id") or auth.get("MEMBER_ID") or "")
    app_sid = merged.get("APP_SID") or auth.get("application_token") or auth.get("APP_SID")
    local_client_id = (
        merged.get("local_client_id")
        or auth.get("local_client_id")
        or merged.get("CLIENT_ID")
        or auth.get("CLIENT_ID")
    )
    local_client_secret = (
        merged.get("local_client_secret")
        or auth.get("local_client_secret")
        or merged.get("CLIENT_SECRET")
        or auth.get("CLIENT_SECRET")
    )
    user_id = merged.get("USER_ID") or auth.get("user_id") or auth.get("USER_ID")
    try:
        user_id = int(user_id) if user_id is not None else None
    except (TypeError, ValueError):
        user_id = None
    return access_token, refresh_token, domain, member_id, app_sid, local_client_id, local_client_secret, user_id


@router.get("/oauth/callback")
def oauth_callback(
    code: str | None = None,
    domain: str | None = None,
    db: Session = Depends(get_db),
):
    s = get_settings()
    if not code or not domain:
        return JSONResponse({"error": "Missing code or domain"}, status_code=400)
    if not s.public_base_url:
        return JSONResponse({"error": "PUBLIC_BASE_URL не настроен"}, status_code=500)
    cid = s.bitrix_app_client_id or s.bitrix_client_id
    csec = s.bitrix_app_client_secret or s.bitrix_client_secret
    if not cid or not csec:
        return JSONResponse({"error": "Bitrix app не настроен"}, status_code=500)
    redirect_uri = f"{s.public_base_url.rstrip('/')}/api/v1/bitrix/oauth/callback"
    result = exchange_code(
        domain, code,
        cid, csec,
        redirect_uri,
    )
    if not result:
        return JSONResponse({"error": "OAuth exchange failed"}, status_code=400)
    domain_clean = _domain_clean(domain)
    domain_full = f"https://{domain_clean}"
    if not user_id and access_token:
        uid, _err = user_current(domain_full, access_token)
        if uid:
            user_id = uid
    portal = db.execute(select(Portal).where(Portal.domain == domain_clean)).scalar_one_or_none()
    if not portal:
        portal = Portal(domain=domain_clean, status="active", install_type="market")
        db.add(portal)
        db.commit()
        db.refresh(portal)
    elif not portal.install_type:
        portal.install_type = "market"
        db.add(portal)
        db.commit()
    save_tokens(
        db, portal.id,
        result.get("access_token", ""),
        result.get("refresh_token", ""),
        int(result.get("expires_in", 3600)),
    )
    return RedirectResponse(url=f"https://{domain_clean}/marketplace/app/", status_code=302)


@router.get("/install")
async def bitrix_install_get():
    """UI-страница установки: загружает BX24 SDK, получает auth через BX24, POST на complete."""
    return _html_ui_response(_load_install_html())


@router.get("/test-iframe")
async def bitrix_test_iframe():
    """Тестовая страница: показывает iframe с /install, чтобы увидеть реальное поведение."""
    html = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Test iframe</title>
  <style>
    body { font-family: system-ui; padding: 1rem; }
    iframe { width: 100%; height: 600px; border: 2px solid #333; }
    pre { background: #f5f5f5; padding: 1rem; overflow: auto; max-height: 200px; }
  </style>
</head>
<body>
  <h1>Тест iframe /install</h1>
  <p>Ниже iframe с src="/api/v1/bitrix/install". Смотрим что там рендерится.</p>
  <iframe id="frame" src="/api/v1/bitrix/install"></iframe>
  <h2>Логи (fetch перехват)</h2>
  <pre id="log">Загрузка...</pre>
</body>
</html>"""
    return HTMLResponse(html)


def _is_install_complete_api_request(request: Request) -> bool:
    """True только если запрос — явный fetch/XHR из install.html с X-Requested-With."""
    # ЖЕЛЕЗОБЕТОННАЯ ЗАЩИТА: JSON только для XHR/fetch, document/iframe — HTML.
    return _is_json_api_request(request)


def _html_install_blocked(request: Request) -> HTMLResponse:
    """HTML for document/iframe navigation to API-only endpoints."""
    url = _install_redirect_url(request)
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Teachbase AI — Установка</title>
  <style>
    body {{ font-family: system-ui; max-width: 560px; margin: 2rem auto; padding: 0 1rem; }}
    .box {{ padding: 0.75rem; background: #fff3cd; border-radius: 4px; }}
    a {{ display: inline-block; margin-top: 0.5rem; }}
  </style>
</head>
<body>
  <h1>Teachbase AI — Установка</h1>
  <div class="box">Этот шаг доступен только через форму установки. Откройте страницу установки.</div>
  <a href="{url}">Перейти к установке</a>
</body>
</html>"""
    return _html_ui_response(html)


def _install_redirect_url(request: Request) -> str:
    s = get_settings()
    base = (s.public_base_url or "").rstrip("/")
    if base and base.startswith("http"):
        return base + "/api/v1/bitrix/install"
    return str(request.base_url).rstrip("/") + "/api/v1/bitrix/install"


def _handler_redirect_url(request: Request) -> str:
    s = get_settings()
    base = (s.public_base_url or "").rstrip("/")
    if base and base.startswith("http"):
        return base + "/api/v1/bitrix/handler"
    return str(request.base_url).rstrip("/") + "/api/v1/bitrix/handler"


def _app_redirect_url(request: Request) -> str:
    s = get_settings()
    base = (s.public_base_url or "").rstrip("/")
    if base and base.startswith("http"):
        return base + "/api/v1/bitrix/install"
    return str(request.base_url).rstrip("/") + "/api/v1/bitrix/install"


@router.get("/app")
async def bitrix_app_get(request: Request):
    """HTML страница «Статус». Document/iframe — всегда 200 HTML. Без интеграции клиент редиректит на install."""
    if _is_json_api_request(request):
        return RedirectResponse(url=_app_redirect_url(request), status_code=303)
    return _html_ui_response(_load_app_html())


class AppStatusBody(BaseModel):
    auth: dict = {}


@router.post("/app/status")
async def bitrix_app_status(request: Request, body: AppStatusBody, db: Session = Depends(get_db)):
    """JSON: статус портала по auth (domain + access_token). XHR only."""
    if not _is_json_api_request(request):
        return RedirectResponse(url=_app_redirect_url(request), status_code=303)
    auth = body.auth or {}
    domain = (auth.get("domain") or auth.get("DOMAIN") or "").strip()
    if not domain:
        return JSONResponse({"installed": False, "error": "missing_domain"}, status_code=400)
    domain_clean = _domain_clean(domain)
    portal = db.execute(select(Portal).where(Portal.domain == domain_clean)).scalar_one_or_none()
    if not portal:
        return JSONResponse({"installed": False}, status_code=404)
    meta = {}
    if portal.metadata_json:
        try:
            meta = json.loads(portal.metadata_json) if isinstance(portal.metadata_json, str) else portal.metadata_json
        except Exception:
            pass
    bot_id = meta.get("bot_id")
    bot_status = "registered" if bot_id else "not_registered"
    rows = db.execute(
        select(PortalUsersAccess).where(PortalUsersAccess.portal_id == portal.id)
    ).scalars().all()
    allowlist = [{"user_id": r.user_id, "name": None} for r in rows]
    from datetime import datetime, timedelta
    from apps.backend.models.event import Event
    since = datetime.utcnow() - timedelta(hours=24)
    events_24h = db.execute(
        select(Event).where(Event.portal_id == portal.id, Event.created_at >= since)
    ).scalars().all()
    in_24h = sum(1 for e in events_24h if e.event_type == "rx")
    blocked_24h = sum(1 for e in events_24h if e.event_type == "blocked_by_acl")
    out_24h = sum(1 for e in events_24h if e.event_type and "tx" in str(e.event_type))
    return JSONResponse({
        "installed": True,
        "domain": portal.domain,
        "bot_status": bot_status,
        "bot_id": bot_id,
        "bot_code": BOT_CODE_DEFAULT,
        "local_creds_present": bool(portal.local_client_id and portal.local_client_secret_encrypted),
        "install_type": portal.install_type or "local",
        "allowlist": allowlist,
        "stats": {"in_24h": in_24h, "out_24h": out_24h, "blocked_24h": blocked_24h},
    })


@router.post("/app/provision")
async def bitrix_app_provision(request: Request, body: AppStatusBody, db: Session = Depends(get_db)):
    """Запуск provision по allowlist. XHR only, auth в body."""
    if not _is_json_api_request(request):
        return RedirectResponse(url=_app_redirect_url(request), status_code=303)
    auth = body.auth or {}
    domain = (auth.get("domain") or auth.get("DOMAIN") or "").strip()
    access_token = auth.get("access_token") or auth.get("ACCESS_TOKEN") or auth.get("AUTH_ID")
    if not domain or not access_token:
        return JSONResponse({"error": "missing_auth"}, status_code=400)
    domain_clean = _domain_clean(domain)
    portal = db.execute(select(Portal).where(Portal.domain == domain_clean)).scalar_one_or_none()
    if not portal:
        return JSONResponse({"error": "portal_not_found"}, status_code=404)
    domain_full = f"https://{domain_clean}" if not domain_clean.startswith("http") else domain_clean
    bot_result = ensure_bot_registered(db, portal.id, _trace_id(request), domain=domain_full, access_token=access_token)
    if not bot_result.get("ok"):
        return JSONResponse({"error": bot_result.get("error_code", "bot_not_registered")}, status_code=400)
    bot_id = bot_result.get("bot_id") or 0
    if not bot_id:
        return JSONResponse({"error": "bot_id_missing"}, status_code=400)
    allowlist_rows = db.execute(
        select(PortalUsersAccess.user_id).where(PortalUsersAccess.portal_id == portal.id)
    ).scalars().all()
    user_ids = []
    for (uid,) in allowlist_rows:
        try:
            user_ids.append(int(uid))
        except (TypeError, ValueError):
            pass
    if not user_ids:
        return JSONResponse({"status": "ok", "ok_count": 0, "failed_count": 0, "trace_id": _trace_id(request)})
    trace_id = _trace_id(request)
    welcome_msg = (getattr(portal, "welcome_message", None) or "").strip() or "Привет! Я Teachbase AI. Напишите «ping» — отвечу «pong»."
    res = step_provision_chats(db, portal.id, domain_full, access_token, bot_id, user_ids, trace_id, welcome_message=welcome_msg)
    return JSONResponse({
        "status": res.get("status"),
        "ok_count": res.get("ok", 0),
        "failed_count": len(res.get("failed", [])),
        "trace_id": trace_id,
        "failed": res.get("failed", []),
    })


@router.post("/app/bot-check")
async def bitrix_app_bot_check(request: Request, body: AppStatusBody, db: Session = Depends(get_db)):
    """Проверка бота imbot.bot.list. XHR only. Возвращает bots_count, sample_bots, found_by, bot_status."""
    if not _is_json_api_request(request):
        return RedirectResponse(url=_app_redirect_url(request), status_code=303)
    auth = body.auth or {}
    domain = (auth.get("domain") or auth.get("DOMAIN") or "").strip()
    access_token = auth.get("access_token") or auth.get("ACCESS_TOKEN") or auth.get("AUTH_ID")
    if not domain or not access_token:
        return JSONResponse({"error": "missing_auth", "bots_count": 0}, status_code=400)
    domain_clean = _domain_clean(domain)
    portal = db.execute(select(Portal).where(Portal.domain == domain_clean)).scalar_one_or_none()
    if not portal:
        return JSONResponse({"error": "portal_not_found", "bots_count": 0}, status_code=404)
    domain_full = f"https://{domain_clean}" if not domain_clean.startswith("http") else domain_clean
    bots, err = imbot_bot_list(domain_full, access_token)
    meta = {}
    if portal.metadata_json:
        try:
            meta = json.loads(portal.metadata_json) if isinstance(portal.metadata_json, str) else portal.metadata_json
        except Exception:
            pass
    our_bot_id = meta.get("bot_id")
    found_by = None
    if our_bot_id and bots:
        for b in bots:
            bid = b.get("id") or b.get("ID")
            if bid is not None and int(bid) == int(our_bot_id):
                found_by = "id"
                break
    if not found_by and bots:
        for b in bots:
            if (b.get("code") or b.get("CODE") or "").strip() == BOT_CODE_DEFAULT:
                found_by = "code"
                break
    bot_found = bool(found_by)
    bot_status = "verified" if bot_found else ("registered_unverified" if our_bot_id else "not_registered")
    sample = (bots[:5] if bots else [])
    sample_bots = [{"id": b.get("id") or b.get("ID"), "code": (b.get("code") or b.get("CODE") or "")[:32]} for b in sample]
    return JSONResponse({
        "bots_count": len(bots),
        "sample_bots": sample_bots,
        "found_by": found_by,
        "bot_found_in_bitrix": bot_found,
        "bot_status": bot_status,
    })


@router.get("/install/complete")
async def bitrix_install_complete_get(request: Request):
    """GET /install/complete не поддерживается как документ — редирект на страницу установки."""
    logger.info("install_complete_mode=document_blocked trace_id=%s method=GET", _trace_id(request))
    return _html_install_blocked(request)


@router.post("/install/complete")
async def bitrix_install_complete(request: Request, db: Session = Depends(get_db)):
    """API only: вызывайте через fetch из install.html. При document navigation — 303 на /install."""
    tid = _trace_id(request)
    if not _is_install_complete_api_request(request):
        logger.info("install_complete_mode=document_blocked trace_id=%s method=POST", tid)
        return _html_install_blocked(request)
    logger.info("install_complete_mode=api trace_id=%s", tid)
    merged = await parse_bitrix_body(request)
    (
        access_token,
        refresh_token,
        domain,
        member_id,
        app_sid,
        local_client_id,
        local_client_secret,
        user_id,
    ) = _parse_install_auth(merged)
    if not domain:
        return JSONResponse(
            {"error": "Missing domain", "status": "error", "trace_id": tid},
            status_code=400,
        )
    if not access_token:
        return JSONResponse(
            {"error": "Missing access_token", "status": "error", "trace_id": tid},
            status_code=400,
        )
    domain_clean = _domain_clean(domain)
    portal = db.execute(select(Portal).where(Portal.domain == domain_clean)).scalar_one_or_none()
    s = get_settings()
    enc_key = s.token_encryption_key or s.secret_key
    if not portal:
        portal = Portal(domain=domain_clean, member_id=member_id, status="active", install_type="local")
        if local_client_id:
            portal.local_client_id = str(local_client_id)
        if local_client_secret and enc_key:
            portal.local_client_secret_encrypted = encrypt_token(str(local_client_secret), enc_key)
        if user_id:
            portal.admin_user_id = user_id
        db.add(portal)
        db.commit()
        db.refresh(portal)
    else:
        portal.member_id = member_id
        if not portal.install_type:
            portal.install_type = "local"
        if local_client_id:
            portal.local_client_id = str(local_client_id)
        if local_client_secret and enc_key:
            portal.local_client_secret_encrypted = encrypt_token(str(local_client_secret), enc_key)
        if user_id:
            portal.admin_user_id = user_id
        db.commit()
    save_tokens(db, portal.id, access_token, refresh_token or "", 3600)
    bot_result = ensure_bot_registered(
        db, portal.id, tid,
        domain=f"https://{portal.domain}",
        access_token=access_token,
    )
    bot_status = "ok" if bot_result.get("ok") else "error"
    bot_payload = {
        "status": bot_status,
        "bot_id_present": bool(bot_result.get("bot_id")),
        "error_code": bot_result.get("error_code"),
        "error_detail_safe": bot_result.get("error_detail_safe"),
    }
    _log_bitrix_install_xhr(tid, portal.id, "complete", request.url.path, 200)
    portal_token = create_portal_token_with_user(portal.id, user_id, expires_minutes=15)
    resp = JSONResponse({
        "status": "ok",
        "trace_id": tid,
        "portal_id": portal.id,
        "portal_token": portal_token,
        "bot": bot_payload,
        "local_creds_present": bool(portal.local_client_id and portal.local_client_secret_encrypted),
        "install_type": portal.install_type or "local",
    })
    resp.headers["X-Trace-Id"] = tid
    return resp


@router.post("/session/start")
async def bitrix_session_start(request: Request, db: Session = Depends(get_db)):
    """Выдаёт portal_token по domain/member_id + access_token (для iframe)."""
    if not _is_json_api_request(request):
        redirect_url = _handler_redirect_url(request)
        return RedirectResponse(url=redirect_url, status_code=303)
    merged = await parse_bitrix_body(request)
    tid = _trace_id(request)
    auth = merged.get("auth", merged)
    if isinstance(auth, str):
        try:
            auth = json.loads(auth) if auth else {}
        except Exception:
            auth = {}
    domain = (merged.get("DOMAIN") or auth.get("domain") or auth.get("DOMAIN") or "").strip()
    member_id = str(merged.get("MEMBER_ID") or auth.get("member_id") or auth.get("MEMBER_ID") or "")
    app_token = merged.get("APP_SID") or auth.get("application_token") or auth.get("APP_SID") or auth.get("APPLICATION_TOKEN")
    access_token = merged.get("AUTH_ID") or auth.get("access_token") or auth.get("ACCESS_TOKEN")
    refresh_token = merged.get("REFRESH_ID") or auth.get("refresh_token") or auth.get("REFRESH_TOKEN")
    user_id = merged.get("USER_ID") or auth.get("user_id") or auth.get("USER_ID")
    try:
        user_id = int(user_id) if user_id is not None else None
    except (TypeError, ValueError):
        user_id = None
    if not domain or not access_token:
        return JSONResponse(
            {"error": "Missing domain or access_token", "trace_id": tid},
            status_code=400,
        )
    domain_clean = _domain_clean(domain)
    portal = db.execute(select(Portal).where(Portal.domain == domain_clean)).scalar_one_or_none()
    if not portal:
        return JSONResponse(
            {"error": "Portal not found", "trace_id": tid},
            status_code=404,
        )
    domain_full = f"https://{portal.domain}"
    if not user_id and access_token:
        uid, _err = user_current(domain_full, access_token)
        if uid:
            user_id = uid
    if not portal.install_type:
        portal.install_type = "local"
        db.add(portal)
        db.commit()
    if member_id and portal.member_id != member_id:
        portal.member_id = member_id
        db.add(portal)
        if not portal.install_type:
            portal.install_type = "local"
        db.commit()
    if app_token and portal.application_token != app_token:
        portal.application_token = str(app_token)
        db.add(portal)
        if not portal.install_type:
            portal.install_type = "local"
        db.commit()
    if user_id and not portal.admin_user_id:
        portal.admin_user_id = user_id
        db.add(portal)
        db.commit()
    if access_token:
        save_tokens(db, portal.id, access_token, refresh_token or "", 3600)
    is_portal_admin = bool(user_id and portal.admin_user_id and int(portal.admin_user_id) == int(user_id))
    portal_token = create_portal_token_with_user(portal.id, user_id, expires_minutes=15)
    return JSONResponse({"portal_token": portal_token, "portal_id": portal.id, "is_portal_admin": is_portal_admin})


@router.get("/users")
async def bitrix_users(
    request: Request,
    portal_id: int,
    start: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    """Список сотрудников портала (user.get). Требует scope user."""
    if pid != portal_id:
        return JSONResponse({"error": "Forbidden", "detail": "portal_id mismatch"}, status_code=403)
    portal = db.execute(select(Portal).where(Portal.id == portal_id)).scalar_one_or_none()
    if not portal:
        return JSONResponse({"error": "Portal not found"}, status_code=404)
    try:
        access_token = get_valid_access_token(db, portal_id, trace_id=_trace_id(request))
    except BitrixAuthError as e:
        return JSONResponse({"error": e.code, "detail": e.detail}, status_code=400)
    domain_full = f"https://{portal.domain}"
    users_list, err = user_get(domain_full, access_token, start=start, limit=limit)
    if err == "missing_scope_user":
        return JSONResponse(
            {"error": "missing_scope_user", "detail": "Не хватает права user. Добавьте право user в приложении Bitrix24 и переустановите."},
            status_code=403,
        )
    if err:
        return JSONResponse({"error": err}, status_code=502)
    out = [
        {
            "id": u.get("ID"),
            "name": u.get("NAME") or "",
            "last_name": u.get("LAST_NAME") or "",
            "email": u.get("EMAIL") or "",
            "active": u.get("ACTIVE") is True,
        }
        for u in users_list
    ]
    return JSONResponse({"users": out, "total": len(out)})


class AccessUsersBody(BaseModel):
    user_ids: list[int]


class FinalizeInstallBody(BaseModel):
    portal_id: int
    selected_user_ids: list[int]
    auth_context: dict = {}


def _require_portal_admin(db: Session, portal_id: int, request: Request) -> Portal:
    portal = db.execute(select(Portal).where(Portal.id == portal_id)).scalar_one_or_none()
    if not portal:
        raise HTTPException(status_code=404, detail="Portal not found")
    uid = _portal_user_id_from_token(request)
    if not uid or not portal.admin_user_id or int(portal.admin_user_id) != int(uid):
        raise HTTPException(status_code=403, detail="Доступ только для администратора портала")
    return portal


@router.get("/portals/{portal_id}/access/users")
async def get_portal_access_users(
    portal_id: int,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    """Список разрешённых user_id портала."""
    if pid != portal_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    rows = db.execute(
        select(PortalUsersAccess).where(PortalUsersAccess.portal_id == portal_id)
    ).scalars().all()
    return JSONResponse({"user_ids": [r.user_id for r in rows]})


@router.get("/portals/{portal_id}/kb/files")
async def get_portal_kb_files(
    portal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    _require_portal_admin(db, portal_id, request)
    q = select(KBFile).where(KBFile.portal_id == portal_id).order_by(KBFile.id.desc()).limit(200)
    files = db.execute(q).scalars().all()
    # show only the latest entry per filename to hide stale errors
    seen: set[str] = set()
    items = []
    for f in files:
        key = (f.filename or f.storage_path or str(f.id)).lower()
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "id": f.id,
            "filename": f.filename,
            "mime_type": f.mime_type,
            "size_bytes": f.size_bytes,
            "status": f.status,
            "error_message": f.error_message,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        })
    return JSONResponse({"items": items})


@router.post("/portals/{portal_id}/kb/files/upload")
async def upload_portal_kb_file(
    portal_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    _require_portal_admin(db, portal_id, request)
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не задан")
    portal_dir = ensure_portal_dir(portal_id)
    safe_name = os.path.basename(file.filename)
    suffix = uuid.uuid4().hex[:8]
    dst_path = os.path.join(portal_dir, f"{suffix}_{safe_name}")
    size, sha256 = save_upload(file.file, dst_path)
    rec = KBFile(
        portal_id=portal_id,
        filename=safe_name,
        mime_type=file.content_type,
        size_bytes=size,
        storage_path=dst_path,
        sha256=sha256,
        status="uploaded",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    job = KBJob(
        portal_id=rec.portal_id,
        job_type="ingest",
        status="queued",
        payload_json={"file_id": rec.id},
    )
    db.add(job)
    db.commit()
    try:
        from redis import Redis
        from rq import Queue
        s = get_settings()
        r = Redis(host=s.redis_host, port=s.redis_port)
        q = Queue("default", connection=r)
        q.enqueue("apps.worker.jobs.process_kb_job", job.id, job_timeout=1800)
    except Exception:
        pass
    return JSONResponse({"id": rec.id, "status": rec.status, "job_id": job.id})


@router.post("/portals/{portal_id}/kb/reindex")
async def reindex_portal_kb(
    portal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    _require_portal_admin(db, portal_id, request)
    files = db.execute(
        select(KBFile).where(
            KBFile.portal_id == portal_id,
            KBFile.status.in_(["uploaded", "error", "queued"]),
        )
    ).scalars().all()
    if not files:
        return JSONResponse({"status": "ok", "queued": 0})
    queued = 0
    try:
        from redis import Redis
        from rq import Queue
        s = get_settings()
        r = Redis(host=s.redis_host, port=s.redis_port)
        q = Queue("default", connection=r)
    except Exception:
        q = None
    for f in files:
        f.status = "queued"
        job = KBJob(
            portal_id=f.portal_id,
            job_type="ingest",
            status="queued",
            payload_json={"file_id": f.id},
        )
        db.add(job)
        db.flush()  # ensure job.id is assigned before enqueue
        job_id = job.id
        queued += 1
        if q:
            try:
                q.enqueue("apps.worker.jobs.process_kb_job", job_id, job_timeout=1800)
            except Exception:
                pass
    db.commit()
    return JSONResponse({"status": "ok", "queued": queued})


@router.post("/portals/{portal_id}/kb/files/{file_id}/reindex")
async def reindex_kb_file(
    portal_id: int,
    file_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    _require_portal_admin(db, portal_id, request)
    rec = db.execute(select(KBFile).where(KBFile.id == file_id, KBFile.portal_id == portal_id)).scalar_one_or_none()
    if not rec:
        return JSONResponse({"error": "not_found"}, status_code=404)
    rec.status = "queued"
    rec.error_message = None
    db.add(rec)
    job = KBJob(
        portal_id=rec.portal_id,
        job_type="ingest",
        status="queued",
        payload_json={"file_id": rec.id},
    )
    db.add(job)
    db.commit()
    try:
        from redis import Redis
        from rq import Queue
        s = get_settings()
        r = Redis(host=s.redis_host, port=s.redis_port)
        q = Queue("default", connection=r)
        q.enqueue("apps.worker.jobs.process_kb_job", job.id, job_timeout=1800)
    except Exception:
        pass
    return JSONResponse({"status": "ok", "job_id": job.id})


@router.delete("/portals/{portal_id}/kb/files/{file_id}")
async def delete_kb_file(
    portal_id: int,
    file_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    _require_portal_admin(db, portal_id, request)
    rec = db.execute(select(KBFile).where(KBFile.id == file_id, KBFile.portal_id == portal_id)).scalar_one_or_none()
    if not rec:
        return JSONResponse({"error": "not_found"}, status_code=404)
    chunk_ids = db.execute(
        select(KBChunk.id).where(KBChunk.file_id == rec.id)
    ).scalars().all()
    if chunk_ids:
        db.execute(delete(KBEmbedding).where(KBEmbedding.chunk_id.in_(chunk_ids)))
        db.execute(delete(KBChunk).where(KBChunk.id.in_(chunk_ids)))
    # remove file from disk
    try:
        if rec.storage_path and os.path.exists(rec.storage_path):
            os.remove(rec.storage_path)
    except Exception:
        pass
    db.execute(delete(KBFile).where(KBFile.id == rec.id))
    db.commit()
    return JSONResponse({"status": "ok"})


@router.get("/portals/{portal_id}/kb/settings")
async def get_portal_kb_settings_api(
    portal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    _require_portal_admin(db, portal_id, request)
    return JSONResponse(get_portal_kb_settings(db, portal_id))


class PortalKBSettingsBody(BaseModel):
    embedding_model: str | None = None
    chat_model: str | None = None
    api_base: str | None = None
    prompt_preset: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    allow_general: bool | None = None
    strict_mode: bool | None = None
    context_messages: int | None = None
    context_chars: int | None = None
    retrieval_top_k: int | None = None
    retrieval_max_chars: int | None = None
    lex_boost: float | None = None
    use_history: bool | None = None
    use_cache: bool | None = None
    system_prompt_extra: str | None = None


class PortalKBSourceBody(BaseModel):
    url: str
    title: str | None = None


@router.post("/portals/{portal_id}/kb/settings")
async def set_portal_kb_settings_api(
    portal_id: int,
    body: PortalKBSettingsBody,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    _require_portal_admin(db, portal_id, request)
    out = set_portal_kb_settings(
        db,
        portal_id,
        body.embedding_model,
        body.chat_model,
        body.api_base,
        body.prompt_preset,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        top_p=body.top_p,
        presence_penalty=body.presence_penalty,
        frequency_penalty=body.frequency_penalty,
        allow_general=body.allow_general,
        strict_mode=body.strict_mode,
        context_messages=body.context_messages,
        context_chars=body.context_chars,
        retrieval_top_k=body.retrieval_top_k,
        retrieval_max_chars=body.retrieval_max_chars,
        lex_boost=body.lex_boost,
        use_history=body.use_history,
        use_cache=body.use_cache,
        system_prompt_extra=body.system_prompt_extra,
    )
    return JSONResponse(out)


@router.get("/portals/{portal_id}/kb/models")
async def get_portal_kb_models(
    portal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    _require_portal_admin(db, portal_id, request)
    # use global token/settings
    from apps.backend.services.kb_settings import get_gigachat_settings, get_gigachat_access_token_plain, get_valid_gigachat_access_token
    settings = get_gigachat_settings(db)
    api_base = settings.get("api_base") or DEFAULT_API_BASE
    token, err = get_valid_gigachat_access_token(db)
    if err or not token:
        return JSONResponse({"error": err or "missing_access_token"}, status_code=400)
    items, err2 = list_models(api_base, token)
    if err2:
        return JSONResponse({"error": err2}, status_code=400)
    return JSONResponse({"items": items})


@router.post("/portals/{portal_id}/kb/sources/url")
async def add_portal_kb_url_source(
    portal_id: int,
    request: Request,
    body: PortalKBSourceBody,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    _require_portal_admin(db, portal_id, request)
    result = create_url_source(db, portal_id, body.url, body.title)
    if not result.get("ok"):
        return JSONResponse({"error": result.get("error")}, status_code=400)
    # enqueue job
    try:
        from redis import Redis
        from rq import Queue
        s = get_settings()
        r = Redis(host=s.redis_host, port=s.redis_port)
        q = Queue("default", connection=r)
        q.enqueue("apps.worker.jobs.process_kb_job", result.get("job_id"), job_timeout=1800)
    except Exception:
        pass
    return JSONResponse(result)


@router.get("/portals/{portal_id}/kb/sources")
async def list_portal_kb_sources(
    portal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    _require_portal_admin(db, portal_id, request)
    q = select(KBSource).where(KBSource.portal_id == portal_id).order_by(KBSource.id.desc()).limit(200)
    rows = db.execute(q).scalars().all()
    # show only latest entry per URL
    seen: set[str] = set()
    items = []
    for s in rows:
        key = (s.url or str(s.id)).strip().lower()
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "id": s.id,
            "url": s.url,
            "title": s.title,
            "source_type": s.source_type,
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        })
    return JSONResponse({"items": items})


@router.get("/portals/{portal_id}/dialogs/recent")
async def get_recent_dialog_messages(
    portal_id: int,
    limit: int = 30,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    """Recent dialog messages for portal (rx/tx) for iframe status page."""
    if pid != portal_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    if limit < 1:
        limit = 1
    if limit > 100:
        limit = 100
    q = (
        select(Message, Dialog)
        .join(Dialog, Dialog.id == Message.dialog_id)
        .where(Dialog.portal_id == portal_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    rows = db.execute(q).all()
    items = []
    for msg, dialog in rows:
        body = (msg.body or "")
        if len(body) > 200:
            body = body[:200] + "…"
        items.append({
            "dialog_id": dialog.provider_dialog_id,
            "direction": msg.direction,
            "body": body,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        })
    return JSONResponse({"items": items, "count": len(items)})


@router.get("/portals/{portal_id}/dialogs/summary")
async def get_dialogs_summary(
    portal_id: int,
    limit: int = 120,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    """Semantic 3-topic summary for recent portal dialogs (iframe analytics widget)."""
    if pid != portal_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    if limit < 10:
        limit = 10
    if limit > 300:
        limit = 300

    from datetime import datetime, timedelta, date
    import json

    today = datetime.utcnow().date()
    latest = (
        db.query(PortalTopicSummary)
        .filter(PortalTopicSummary.portal_id == portal_id)
        .filter(PortalTopicSummary.day == today)
        .order_by(PortalTopicSummary.created_at.desc())
        .first()
    )
    if latest:
        return JSONResponse(
            {
                "items": latest.items or [],
                "day": latest.day.isoformat(),
                "count": len(latest.items or []),
                "stale": False,
            }
        )

    day_start = datetime.combine(today, datetime.min.time())
    day_end = day_start + timedelta(days=1)
    q = (
        select(Message.body)
        .join(Dialog, Dialog.id == Message.dialog_id)
        .where(Dialog.portal_id == portal_id)
        .where(Message.direction == "rx")
        .where(Message.body.isnot(None))
        .where(Message.created_at >= day_start)
        .where(Message.created_at < day_end)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    rows = db.execute(q).scalars().all()
    texts = [str(t).strip() for t in rows if t and str(t).strip()]

    source_from = day_start
    source_to = day_end
    if len(texts) < 10:
        week_start = datetime.utcnow() - timedelta(days=7)
        q = (
            select(Message.body)
            .join(Dialog, Dialog.id == Message.dialog_id)
            .where(Dialog.portal_id == portal_id)
            .where(Message.direction == "rx")
            .where(Message.body.isnot(None))
            .where(Message.created_at >= week_start)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        rows = db.execute(q).scalars().all()
        texts = [str(t).strip() for t in rows if t and str(t).strip()]
        source_from = week_start
        source_to = datetime.utcnow()

    if len(texts) < 8:
        last = (
            db.query(PortalTopicSummary)
            .filter(PortalTopicSummary.portal_id == portal_id)
            .order_by(PortalTopicSummary.day.desc())
            .first()
        )
        if last:
            return JSONResponse(
                {
                    "items": last.items or [],
                    "day": last.day.isoformat(),
                    "count": len(last.items or []),
                    "stale": True,
                }
            )
        return JSONResponse({"items": [], "count": len(texts)}, status_code=200)

    settings = get_effective_gigachat_settings(db, portal_id)
    token, err = get_valid_gigachat_access_token(db)
    if err:
        return JSONResponse({"error": "gigachat_unavailable"}, status_code=503)

    sample = "\n".join(texts[:160])
    system = (
        "Ты аналитик запросов. На входе список пользовательских сообщений. "
        "Сгруппируй по смыслу в 3 главные темы. Для каждой темы верни одно "
        "осмысленное предложение на русском и оценку частоты (score) от 1 до 100 "
        "по относительной популярности. Формат строго JSON массив из 3 объектов "
        "с полями: topic, score."
    )
    user = (
        "Сообщения:\n" + sample + "\n\n"
        "Верни JSON массив из 3 объектов. Никакого текста вокруг JSON."
    )
    content, err2, _usage = chat_complete(
        settings.get("api_base") or DEFAULT_API_BASE,
        token,
        settings.get("chat_model") or "GigaChat-2-Pro",
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        max_tokens=260,
    )
    items: list[dict] = []
    if not err2 and content:
        try:
            data = json.loads(str(content).strip())
            if isinstance(data, list):
                for it in data:
                    topic = str(it.get("topic", "")).strip()
                    score = it.get("score")
                    if topic:
                        try:
                            score_int = int(score)
                        except Exception:
                            score_int = None
                        items.append({"topic": topic, "score": score_int})
        except Exception:
            items = []

    if len(items) >= 3:
        rec = PortalTopicSummary(
            portal_id=portal_id,
            day=today,
            source_from=source_from,
            source_to=source_to,
            items=items,
        )
        db.add(rec)
        db.commit()
        return JSONResponse(
            {
                "items": items,
                "day": today.isoformat(),
                "count": len(items),
                "stale": False,
            }
        )

    last = (
        db.query(PortalTopicSummary)
        .filter(PortalTopicSummary.portal_id == portal_id)
        .order_by(PortalTopicSummary.day.desc())
        .first()
    )
    if last:
        return JSONResponse(
            {
                "items": last.items or [],
                "day": last.day.isoformat(),
                "count": len(last.items or []),
                "stale": True,
            }
        )
    return JSONResponse({"items": [], "error": "summary_failed"}, status_code=200)


@router.get("/portals/{portal_id}/users/stats")
async def get_portal_user_stats(
    portal_id: int,
    hours: int = 24,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    if hours < 1:
        hours = 1
    if hours > 168:
        hours = 168
    from datetime import datetime, timedelta
    since = datetime.utcnow() - timedelta(hours=hours)
    q = (
        db.query(BitrixInboundEvent.user_id, func.count(BitrixInboundEvent.id))
        .filter(BitrixInboundEvent.portal_id == portal_id)
        .filter(BitrixInboundEvent.event_name == "ONIMBOTMESSAGEADD")
        .filter(BitrixInboundEvent.created_at >= since)
        .group_by(BitrixInboundEvent.user_id)
    )
    stats = {str(uid): int(cnt) for uid, cnt in q.all() if uid is not None}
    return JSONResponse({"hours": hours, "stats": stats})


@router.get("/portals/{portal_id}/billing/summary")
async def get_portal_billing_summary(
    portal_id: int,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    return JSONResponse(get_portal_usage_summary(db, portal_id))


@router.put("/portals/{portal_id}/access/users")
async def put_portal_access_users(
    portal_id: int,
    body: AccessUsersBody,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    """Bulk replace allowlist. user_ids — список Bitrix user ID."""
    if pid != portal_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    prev_rows = db.execute(
        select(PortalUsersAccess.user_id).where(PortalUsersAccess.portal_id == portal_id)
    ).scalars().all()
    prev_set = set(str(u) for u in prev_rows)
    user_ids_str = [str(uid) for uid in body.user_ids]
    new_set = set(user_ids_str)

    db.execute(delete(PortalUsersAccess).where(PortalUsersAccess.portal_id == portal_id))
    for uid in user_ids_str:
        db.add(PortalUsersAccess(portal_id=portal_id, user_id=uid))
    db.commit()

    added = sorted(list(new_set - prev_set))
    welcome_status = "skipped"
    welcome_error = None
    if added:
        portal = db.execute(select(Portal).where(Portal.id == portal_id)).scalar_one_or_none()
        if portal and portal.domain:
            access_token = get_access_token(db, portal_id)
            if access_token:
                trace_id = _now_trace_id()
                bot_res = ensure_bot_registered(
                    db,
                    portal_id,
                    trace_id,
                    domain=portal.domain,
                    access_token=access_token,
                    force=False,
                )
                bot_id = int(bot_res.get("bot_id") or 0)
                if bot_res.get("ok") and bot_id:
                    try:
                        added_ids = [int(u) for u in added if str(u).isdigit()]
                        if added_ids:
                            res = step_provision_chats(
                                db,
                                portal_id,
                                portal.domain,
                                access_token,
                                bot_id,
                                added_ids,
                                trace_id,
                                welcome_message=(getattr(portal, "welcome_message", None) or "").strip() or None,
                            )
                            welcome_status = res.get("status", "error")
                        else:
                            welcome_status = "skipped"
                    except Exception as e:
                        welcome_status = "error"
                        welcome_error = str(e)[:120]
                else:
                    welcome_status = "error"
                    welcome_error = bot_res.get("error_code") or "bot_not_registered"
            else:
                welcome_status = "skipped"
                welcome_error = "missing_access_token"
        else:
            welcome_status = "skipped"
            welcome_error = "missing_portal_domain"

    return JSONResponse({
        "status": "ok",
        "count": len(user_ids_str),
        "welcome": {"status": welcome_status, "error": welcome_error, "added": added},
    })


@router.post("/install")
async def bitrix_install_post(request: Request, db: Session = Depends(get_db)):
    """Fallback: Bitrix POST с AUTH_ID в query/form. Если нет токена — отдаём HTML UI."""
    if not _is_json_api_request(request):
        return _html_ui_response(_load_install_html())
    merged = await parse_bitrix_body(request)
    tid = _trace_id(request)
    (
        access_token,
        refresh_token,
        domain,
        member_id,
        app_sid,
        local_client_id,
        local_client_secret,
        user_id,
    ) = _parse_install_auth(merged)
    if not domain:
        return JSONResponse(
            {"error": "Missing domain", "status": "error", "trace_id": tid},
            status_code=400,
        )
    if not access_token:
        return _html_ui_response(_load_install_html())
    domain_clean = _domain_clean(domain)
    s = get_settings()
    enc_key = s.token_encryption_key or s.secret_key
    portal = db.execute(select(Portal).where(Portal.domain == domain_clean)).scalar_one_or_none()
    if not portal:
        portal = Portal(domain=domain_clean, member_id=str(member_id), status="active", install_type="local")
        if local_client_id:
            portal.local_client_id = str(local_client_id)
        if local_client_secret and enc_key:
            portal.local_client_secret_encrypted = encrypt_token(str(local_client_secret), enc_key)
        if user_id:
            portal.admin_user_id = user_id
        db.add(portal)
        db.commit()
        db.refresh(portal)
    else:
        portal.member_id = str(member_id)
        if not portal.install_type:
            portal.install_type = "local"
        if local_client_id:
            portal.local_client_id = str(local_client_id)
        if local_client_secret and enc_key:
            portal.local_client_secret_encrypted = encrypt_token(str(local_client_secret), enc_key)
        if user_id and not portal.admin_user_id:
            portal.admin_user_id = user_id
        db.commit()
    save_tokens(db, portal.id, access_token, refresh_token or "", 3600)
    portal_token = create_portal_token_with_user(portal.id, user_id, expires_minutes=15)
    return JSONResponse({"status": "ok", "portal_id": portal.id, "portal_token": portal_token})


@router.post("/install/finalize")
async def bitrix_install_finalize(
    request: Request,
    body: FinalizeInstallBody,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    """Finalize install: allowlist -> ensure bot -> provision chats. XHR only."""
    if not _is_json_api_request(request):
        return RedirectResponse(url=_install_redirect_url(request), status_code=303)
    if pid != body.portal_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    trace_id = _trace_id(request)
    try:
        result = finalize_install(
            db,
            portal_id=body.portal_id,
            selected_user_ids=body.selected_user_ids,
            auth_context=body.auth_context or {},
            trace_id=trace_id,
        )
        status_code = 200
        _log_bitrix_install_xhr(
            trace_id, body.portal_id, "finalize", request.url.path, status_code,
        )
        resp = JSONResponse(result)
        resp.headers["X-Trace-Id"] = trace_id
        return resp
    except Exception as e:
        safe_err = str(e)[:200].replace("'", "")
        _log_bitrix_install_xhr(
            trace_id, body.portal_id, "finalize", request.url.path, 500,
            err_code="internal_error", safe_err=safe_err,
        )
        resp = JSONResponse(
            {"error": "internal_error", "trace_id": trace_id},
            status_code=500,
        )
        resp.headers["X-Trace-Id"] = trace_id
        return resp


@router.api_route("/handler", methods=["GET", "POST"])
async def bitrix_handler(request: Request, db: Session = Depends(get_db)):
    """Обработчик: placement (GET) — HTML UI с управлением доступом, события (POST) — JSON."""
    if _is_document_navigation(request):
        return _html_ui_response(_load_handler_html())
    merged = await parse_bitrix_body(request)
    tid = _trace_id(request)
    event = (merged.get("event", "") or "").strip()
    data = merged.get("data", merged)
    auth = merged.get("auth", {})
    if isinstance(auth, str):
        try:
            auth = json.loads(auth) if auth else {}
        except Exception:
            auth = {}
    if not isinstance(auth, dict):
        auth = {}
    if not event:
        # Bitrix placement иногда приходит POST без event — отдаём HTML, не JSON.
        return _html_ui_response(_load_handler_html())
    if event == "ONIMBOTMESSAGEADD":
        result = process_imbot_message(db, data, auth)
        return JSONResponse(result)
    return JSONResponse({"status": "ok", "event": event, "trace_id": tid})


@router.get("/events")
async def bitrix_events_get(request: Request):
    """Bitrix/checks: GET /v1/bitrix/events -> 200 JSON so Bitrix URL checks don't get 405."""
    if _is_document_navigation(request):
        return _html_ui_response(_load_handler_html())
    return JSONResponse(
        {"status": "ok", "method": "GET", "note": "events endpoint accepts POST"},
        status_code=200,
    )


@router.head("/events")
async def bitrix_events_head(request: Request):
    """Bitrix/checks: HEAD /v1/bitrix/events -> 200 JSON."""
    if _is_document_navigation(request):
        return _html_ui_response(_load_handler_html())
    return JSONResponse(
        {"status": "ok", "method": "HEAD", "note": "events endpoint accepts POST"},
        status_code=200,
    )


@router.options("/events")
async def bitrix_events_options():
    """Bitrix/checks: OPTIONS /v1/bitrix/events -> 200 OK (CORS)."""
    return PlainTextResponse("", status_code=200)


@router.post("/events")
async def bitrix_events(request: Request, db: Session = Depends(get_db)):
    if _is_document_navigation(request):
        return _html_ui_response(_load_handler_html())
    merged = await parse_bitrix_body(request)
    tid = _trace_id(request)
    event = merged.get("event", "")
    data = merged.get("data", merged)
    auth = merged.get("auth", {})
    if isinstance(auth, str):
        try:
            auth = json.loads(auth) if auth else {}
        except Exception:
            auth = {}
    if not isinstance(auth, dict):
        auth = {}
    if event == "ONIMBOTMESSAGEADD":
        result = process_imbot_message(db, data, auth)
        return JSONResponse(result)
    return JSONResponse({"status": "ok", "event": event, "trace_id": tid})


@router.post("/placement")
async def bitrix_placement(request: Request):
    return JSONResponse({"status": "ok"})
