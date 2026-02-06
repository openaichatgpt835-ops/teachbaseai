"""Админские endpoints для порталов."""
import json
import logging
import time
import uuid
import hashlib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, delete, desc

from apps.backend.deps import get_db
from apps.backend.auth import get_current_admin
from apps.backend.models.portal import Portal, PortalUsersAccess, PortalToken
from apps.backend.models.event import Event
from apps.backend.models.bitrix_log import BitrixHttpLog
from apps.backend.services.portal_tokens import BitrixAuthError, ensure_fresh_access_token
from apps.backend.services.token_crypto import encrypt_token
from apps.backend.config import get_settings
from apps.backend.services.bitrix_auth import rest_call_with_refresh
from apps.backend.services.bot_provisioning import ensure_bot_registered, ensure_bot_handlers, reset_portal_bot
from apps.backend.services.chat_provisioning import provision_welcome_chats
from apps.backend.clients.bitrix import (
    BOT_CODE_DEFAULT,
    _normalize_bot_list_result,
)
from apps.backend.services.bitrix_logging import log_outbound_imbot_bot_list, log_outbound_imbot_message_add

router = APIRouter()
logger = logging.getLogger(__name__)


class PortalCreate(BaseModel):
    domain: str
    member_id: str | None = None


class PortalUpdate(BaseModel):
    status: str | None = None
    metadata_json: str | None = None


class AccessUsersBody(BaseModel):
    user_ids: list[str]


class BitrixCredentialsBody(BaseModel):
    client_id: str
    client_secret: str


@router.get("")
def list_portals(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    q = select(Portal).offset(skip).limit(limit).order_by(Portal.id.desc())
    portals = db.execute(q).scalars().all()
    return {"items": [{"id": p.id, "domain": p.domain, "status": p.status} for p in portals]}


@router.post("")
def create_portal(
    data: PortalCreate,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    existing = db.execute(select(Portal).where(Portal.domain == data.domain)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Портал с таким доменом уже есть")
    p = Portal(domain=data.domain, member_id=data.member_id)
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"id": p.id, "domain": p.domain, "status": p.status}


@router.get("/{portal_id}")
def get_portal(
    portal_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    p = db.get(Portal, portal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Портал не найден")
    rows = db.execute(
        select(PortalUsersAccess).where(PortalUsersAccess.portal_id == portal_id)
    ).scalars().all()
    return {
        "id": p.id,
        "domain": p.domain,
        "member_id": p.member_id,
        "status": p.status,
        "metadata_json": p.metadata_json,
        "welcome_message": getattr(p, "welcome_message", None) or "Привет! Я Teachbase AI. Напишите «ping» — отвечу «pong».",
        "allowed_user_ids": [r.user_id for r in rows],
    }


@router.patch("/{portal_id}")
def update_portal(
    portal_id: int,
    data: PortalUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    p = db.get(Portal, portal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Портал не найден")
    if data.status is not None:
        p.status = data.status
    if data.metadata_json is not None:
        p.metadata_json = data.metadata_json
    db.commit()
    db.refresh(p)
    return {"id": p.id, "status": p.status}


@router.get("/{portal_id}/access/users")
def get_portal_access_users(
    portal_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    p = db.get(Portal, portal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Портал не найден")
    rows = db.execute(
        select(PortalUsersAccess).where(PortalUsersAccess.portal_id == portal_id)
    ).scalars().all()
    return {"user_ids": [r.user_id for r in rows]}


@router.put("/{portal_id}/access/users")
def put_portal_access_users(
    portal_id: int,
    data: AccessUsersBody,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    p = db.get(Portal, portal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Портал не найден")
    db.execute(delete(PortalUsersAccess).where(PortalUsersAccess.portal_id == portal_id))
    for uid in data.user_ids:
        db.add(PortalUsersAccess(portal_id=portal_id, user_id=str(uid)))
    db.commit()
    return {"status": "ok", "count": len(data.user_ids)}


class WelcomeMessageBody(BaseModel):
    welcome_message: str


@router.put("/{portal_id}/welcome_message")
def put_portal_welcome_message(
    portal_id: int,
    data: WelcomeMessageBody,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    """Обновить приветственное сообщение портала (используется при provision чатов)."""
    p = db.get(Portal, portal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Портал не найден")
    old_val = getattr(p, "welcome_message", None) or ""
    p.welcome_message = (data.welcome_message or "").strip() or "Привет! Я Teachbase AI. Напишите «ping» — отвечу «pong»."
    db.add(p)
    db.commit()
    db.add(Event(
        portal_id=portal_id,
        provider_event_id="admin_welcome",
        event_type="admin_welcome_message_updated",
        payload_json=json.dumps({"portal_id": portal_id}, ensure_ascii=False),
    ))
    db.commit()
    logger.info("admin_welcome_message_updated portal_id=%s", portal_id)
    return {"status": "ok", "welcome_message": p.welcome_message}


def _portal_bot_status_from_meta(meta: dict | None) -> str:
    if not meta:
        return "not_registered"
    if meta.get("bot_id") and meta.get("bot_app_token_enc"):
        return "registered"
    if meta.get("bot_id"):
        return "registered"
    return "not_registered"


@router.get("/{portal_id}/bot/status")
def admin_portal_bot_status(
    portal_id: int,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    """Статус бота по порталу + последние N попыток imbot_register (request_shape/response_shape без секретов)."""
    p = db.get(Portal, portal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Портал не найден")
    meta = {}
    if p.metadata_json:
        try:
            meta = json.loads(p.metadata_json) if isinstance(p.metadata_json, str) else p.metadata_json
        except Exception:
            pass
    status = _portal_bot_status_from_meta(meta)
    bot_id = meta.get("bot_id")
    rows = (
        db.execute(
            select(BitrixHttpLog)
            .where(BitrixHttpLog.portal_id == portal_id, BitrixHttpLog.kind == "imbot_register")
            .order_by(desc(BitrixHttpLog.created_at))
            .limit(limit)
        )
        .scalars().all()
    )
    last_attempts = []
    for r in rows:
        summary = {}
        if r.summary_json:
            try:
                summary = json.loads(r.summary_json) if isinstance(r.summary_json, str) else r.summary_json
            except Exception:
                pass
        req = summary.get("request_shape_json") or {}
        last_attempts.append({
            "trace_id": r.trace_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "status_code": r.status_code,
            "error_code": summary.get("error_code"),
            "error_description_safe": summary.get("error_description_safe"),
            "request_shape_json": req,
            "response_shape_json": summary.get("response_shape_json"),
            "event_urls_sent": summary.get("event_urls_sent"),
            "content_type_sent": req.get("content_type_sent"),
            "api_prefix_used": req.get("api_prefix_used"),
        })
    prepare_rows = db.execute(
        select(BitrixHttpLog)
        .where(BitrixHttpLog.portal_id == portal_id, BitrixHttpLog.kind == "prepare_chats")
        .order_by(desc(BitrixHttpLog.created_at))
        .limit(limit)
    ).scalars().all()
    last_prepare_chats = []
    for r in prepare_rows:
        summary_pc = {}
        if r.summary_json:
            try:
                summary_pc = json.loads(r.summary_json) if isinstance(r.summary_json, str) else r.summary_json
            except Exception:
                pass
        last_prepare_chats.append({
            "trace_id": r.trace_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "status": summary_pc.get("status"),
            "total": summary_pc.get("total"),
            "ok_count": summary_pc.get("ok_count"),
            "users_failed": summary_pc.get("users_failed"),
            "failed": summary_pc.get("failed"),
        })
    return {
        "portal_id": portal_id,
        "status": status,
        "bot_id": bot_id,
        "last_attempts": last_attempts,
        "last_prepare_chats": last_prepare_chats,
    }


def _safe_bot_sample(bot: dict) -> dict:
    """Только id, code, name (без токенов)."""
    bid = bot.get("BOT_ID") or bot.get("bot_id") or bot.get("ID") or bot.get("id")
    code = (bot.get("CODE") or bot.get("code") or "")[:64]
    name = (bot.get("NAME") or bot.get("name") or "")[:128]
    return {"id": bid, "code": code, "name": name}


@router.post("/{portal_id}/bot/check")
def admin_portal_bot_check(
    portal_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    """Проверка наличия бота в Bitrix (imbot.bot.list). Логируем в bitrix_http_logs kind=imbot_bot_list."""
    p = db.get(Portal, portal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Портал не найден")
    trace_id = str(uuid.uuid4())[:16]
    domain = (p.domain or "").strip()
    if not domain:
        return {
            "trace_id": trace_id,
            "portal_id": portal_id,
            "status": "error",
            "error_code": "missing_auth",
            "bot_found_in_bitrix": False,
        }
    t0 = time.perf_counter()
    result, err, err_desc, status_code, refreshed = rest_call_with_refresh(
        db, portal_id, "imbot.bot.list", {}, trace_id, timeout_sec=10
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)
    if err or not result:
        log_outbound_imbot_bot_list(
            db, trace_id, portal_id,
            status_code or 0, latency_ms,
            bitrix_error_code=err,
            bitrix_error_desc=err_desc or None,
            bots_count=0,
            found_by="none",
            sample_bots=[],
            refreshed=refreshed,
        )
        return {
            "trace_id": trace_id,
            "portal_id": portal_id,
            "status": "error",
            "error_code": err or "rest_error",
            "bot_found_in_bitrix": False,
            "notes": "Set per-portal client_id/client_secret in Admin → Portal → OAuth" if err == "missing_client_credentials" else None,
        }
    bots = _normalize_bot_list_result(result)
    meta = {}
    if p.metadata_json:
        try:
            meta = json.loads(p.metadata_json) if isinstance(p.metadata_json, str) else p.metadata_json
        except Exception:
            pass
    our_bot_id = meta.get("bot_id")
    found_by_val = "none"
    for b in bots:
        if not isinstance(b, dict):
            continue
        code = (b.get("CODE") or b.get("code") or "").strip()
        bid = b.get("BOT_ID") or b.get("bot_id") or b.get("ID") or b.get("id")
        if code == BOT_CODE_DEFAULT:
            found_by_val = "code"
            break
        if our_bot_id and bid is not None:
            try:
                if int(bid) == int(our_bot_id):
                    found_by_val = "id"
                    break
            except (TypeError, ValueError):
                pass
    sample_bots = [_safe_bot_sample(b) for b in bots[:5]]
    log_outbound_imbot_bot_list(
        db, trace_id, portal_id,
        status_code or 200, latency_ms,
        bitrix_error_code=None,
        bitrix_error_desc=None,
        bots_count=len(bots),
        found_by=found_by_val,
        sample_bots=sample_bots,
        refreshed=refreshed,
    )
    return {
        "trace_id": trace_id,
        "portal_id": portal_id,
        "status": "ok",
        "bot_found_in_bitrix": found_by_val != "none",
        "bots_count": len(bots),
        "found_by": found_by_val,
    }


@router.post("/{portal_id}/bot/fix-handlers")
def admin_portal_bot_fix_handlers(
    portal_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    """Починить handler URL бота (EVENT_MESSAGE_ADD и др.) через imbot.update. Возвращает ok, trace_id, bot_id, error_code."""
    trace_id = str(uuid.uuid4())[:16]
    result = ensure_bot_handlers(db, portal_id, trace_id)
    out = {
        "trace_id": trace_id,
        "portal_id": portal_id,
        "ok": result.get("ok", False),
        "bot_id": result.get("bot_id"),
        "error_code": result.get("error_code"),
        "event_urls_sent": result.get("event_urls_sent", []),
        "notes": result.get("notes", ""),
    }
    return out


@router.post("/{portal_id}/bot/ping")
def admin_portal_bot_ping(
    portal_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    """Отправить "ping" пользователю из allowlist (imbot.message.add) и ожидать inbound ONIMBOTMESSAGEADD."""
    p = db.get(Portal, portal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Портал не найден")
    trace_id = str(uuid.uuid4())[:16]
    rows = db.execute(
        select(PortalUsersAccess).where(PortalUsersAccess.portal_id == portal_id)
    ).scalars().all()
    user_ids = []
    for r in rows:
        try:
            user_ids.append(int(r.user_id))
        except (TypeError, ValueError):
            pass
    if not user_ids:
        return {"ok": False, "trace_id": trace_id, "error_code": "allowlist_empty", "notes": "Нет пользователей в allowlist"}
    meta = {}
    if p.metadata_json:
        try:
            meta = json.loads(p.metadata_json) if isinstance(p.metadata_json, str) else p.metadata_json
        except Exception:
            pass
    bot_id = meta.get("bot_id")
    if not bot_id:
        return {"ok": False, "trace_id": trace_id, "error_code": "bot_not_registered", "notes": "Бот не зарегистрирован"}
    domain = (p.domain or "").strip()
    domain_full = f"https://{domain}" if domain and not domain.startswith("http") else domain or None
    if not domain_full:
        return {"ok": False, "trace_id": trace_id, "error_code": "missing_auth", "notes": "Нет домена портала"}
    user_id = user_ids[0]
    dialog_id = str(user_id)
    params = {"BOT_ID": int(bot_id), "DIALOG_ID": dialog_id, "MESSAGE": "ping"}
    t0 = time.perf_counter()
    result, err, err_desc, status_code, _ = rest_call_with_refresh(
        db, portal_id, "imbot.message.add", params, trace_id, timeout_sec=15
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)
    ok = result is not None and not err
    log_outbound_imbot_message_add(
        db, trace_id, portal_id, user_id, dialog_id,
        status_code=status_code, latency_ms=latency_ms,
        bitrix_error_code=err,
        bitrix_error_desc=err_desc or None,
    )
    return {
        "ok": ok,
        "trace_id": trace_id,
        "user_id": user_id,
        "dialog_id": dialog_id,
        "notes": "Проверьте inbound-events по ONIMBOTMESSAGEADD с MESSAGE=ping; ожидается ответ pong от бота." if ok else (err or "send_failed"),
    }

@router.post("/{portal_id}/auth/refresh-bitrix")
def admin_portal_refresh_bitrix_token(
    portal_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    """Принудительное обновление Bitrix OAuth токенов (для диагностики)."""
    trace_id = str(uuid.uuid4())[:16]
    try:
        token = ensure_fresh_access_token(db, portal_id, trace_id=trace_id, force=True)
        _ = token  # token is not returned
    except BitrixAuthError as e:
        return {
            "ok": False,
            "trace_id": trace_id,
            "portal_id": portal_id,
            "error_code": e.code,
            "notes": e.detail,
        }
    row = db.execute(select(PortalToken).where(PortalToken.portal_id == portal_id)).scalar_one_or_none()
    expires_in = int((row.expires_at - row.updated_at).total_seconds()) if row and row.expires_at and row.updated_at else 0
    expires_at = row.expires_at.isoformat() if row and row.expires_at else None
    return {
        "ok": True,
        "trace_id": trace_id,
        "portal_id": portal_id,
        "expires_in": expires_in,
        "expires_at": expires_at,
    }


@router.get("/{portal_id}/auth/status")
def admin_portal_auth_status(
    portal_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    p = db.get(Portal, portal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Портал не найден")
    row = db.execute(select(PortalToken).where(PortalToken.portal_id == portal_id)).scalar_one_or_none()
    has_client_id = bool((p.local_client_id or "").strip())
    has_client_secret = bool(p.local_client_secret_encrypted)
    has_access_token = bool(row and row.access_token)
    has_refresh_token = bool(row and row.refresh_token)
    expires_at = row.expires_at.isoformat() if row and row.expires_at else None
    expired = False
    if row and row.expires_at:
        expired = row.expires_at <= datetime.utcnow()
    s = get_settings()
    base = (s.public_base_url or "").rstrip("/")
    events_url_expected = f"{base}/v1/bitrix/events" if base else None
    using_global_env = bool(s.bitrix_client_id and s.bitrix_client_secret)
    return {
        "portal_id": portal_id,
        "has_local_client_id": has_client_id,
        "has_local_client_secret": has_client_secret,
        "using_global_env": using_global_env,
        "has_access_token": has_access_token,
        "has_refresh_token": has_refresh_token,
        "expires_at": expires_at,
        "expired": expired,
        "events_url_expected": events_url_expected,
    }


@router.post("/{portal_id}/auth/set-local-credentials")
def admin_portal_set_bitrix_credentials(
    portal_id: int,
    data: BitrixCredentialsBody,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    p = db.get(Portal, portal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Портал не найден")
    client_id = (data.client_id or "").strip()
    client_secret = (data.client_secret or "").strip()
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="client_id/client_secret required")
    s = get_settings()
    enc = s.token_encryption_key or s.secret_key
    p.local_client_id = client_id
    p.local_client_secret_encrypted = encrypt_token(client_secret, enc)
    db.add(p)
    db.commit()
    return {
        "ok": True,
        "portal_id": portal_id,
        "client_id_masked": f"{client_id[:6]}...{client_id[-4:]}" if len(client_id) > 10 else f"{client_id[:2]}...{client_id[-2:]}",
        "client_secret_len": len(client_secret),
        "client_secret_sha256": hashlib.sha256(client_secret.encode()).hexdigest()[:12],
    }


@router.post("/{portal_id}/bot/reset")
def admin_portal_bot_reset(
    portal_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    """Удалить только наших ботов (CODE=teachbase_assistant), зарегистрировать заново, починить handlers. Без секретов в ответе."""
    trace_id = str(uuid.uuid4())[:16]
    result = reset_portal_bot(db, portal_id, trace_id)
    return {
        "trace_id": trace_id,
        "portal_id": portal_id,
        "ok": result.get("ok", False),
        "deleted_count": result.get("deleted_count", 0),
        "registered_bot_id": result.get("registered_bot_id"),
        "notes": result.get("notes", ""),
        "error_code": result.get("error_code"),
        "sample_bots": result.get("sample_bots"),
    }


@router.post("/{portal_id}/bot/provision_welcome")
def admin_portal_bot_provision_welcome(
    portal_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    """Отправить welcome каждому из allowlist (бот пишет первым). AUTH: admin JWT."""
    p = db.get(Portal, portal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Портал не найден")
    rows = db.execute(
        select(PortalUsersAccess).where(PortalUsersAccess.portal_id == portal_id)
    ).scalars().all()
    user_ids = []
    for r in rows:
        try:
            user_ids.append(int(r.user_id))
        except (TypeError, ValueError):
            pass
    if not user_ids:
        return {
            "trace_id": str(uuid.uuid4())[:16],
            "portal_id": portal_id,
            "status": "ok",
            "message": "allowlist пуст",
            "ok_count": 0,
            "fail_count": 0,
            "results": [],
        }
    trace_id = str(uuid.uuid4())[:16]
    result = provision_welcome_chats(db, portal_id, user_ids, trace_id)
    return {
        "trace_id": trace_id,
        "portal_id": portal_id,
        "status": "ok" if result.get("fail_count", 0) == 0 else "partial_fail",
        "ok_count": result.get("ok_count", 0),
        "fail_count": result.get("fail_count", 0),
        "results": result.get("results", []),
    }


@router.post("/{portal_id}/bot/register")
def admin_portal_bot_register(
    portal_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    """Принудительная регистрация бота (диагностический рычаг). AUTH: admin JWT."""
    p = db.get(Portal, portal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Портал не найден")
    trace_id = str(uuid.uuid4())[:16]
    raw_domain = (p.domain or "").strip()
    domain_full = f"https://{raw_domain}" if raw_domain and not raw_domain.startswith("http") else raw_domain or None
    result = ensure_bot_registered(
        db, portal_id, trace_id,
        domain=domain_full or None,
        access_token=None,
        force=True,
    )
    db.add(Event(
        portal_id=portal_id,
        provider_event_id=trace_id,
        event_type="bot_register",
        payload_json=json.dumps({
            "trace_id": trace_id,
            "status": "ok" if result.get("ok") else "error",
            "error_code": result.get("error_code"),
            "error_description_safe": (result.get("error_detail_safe") or "")[:200],
            "event_urls_sent": result.get("event_urls_sent") or [],
        }, ensure_ascii=False),
    ))
    db.commit()
    return {
        "status": "ok" if result.get("ok") else "error",
        "trace_id": trace_id,
        "portal_id": portal_id,
        "bot": {
            "status": "ok" if result.get("ok") else "error",
            "bot_id_present": bool(result.get("bot_id")),
            "error_code": result.get("error_code"),
            "error_description_safe": result.get("error_detail_safe"),
        },
        "event_urls_sent": result.get("event_urls_sent") or [],
    }


@router.post("/{portal_id}/setup")
def portal_setup(
    portal_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    p = db.get(Portal, portal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Портал не найден")
    # Placeholder: проверки, создание чатов и т.д.
    return {"status": "ok", "message": "Setup выполнено"}


@router.post("/{portal_id}/diagnostics")
def portal_diagnostics(
    portal_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    p = db.get(Portal, portal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Портал не найден")
    return {"portal_id": portal_id, "status": p.status, "checks": []}


@router.post("/{portal_id}/attempt-fix")
def portal_attempt_fix(
    portal_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    p = db.get(Portal, portal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Портал не найден")
    return {"status": "ok", "message": "Попытка исправления выполнена"}
