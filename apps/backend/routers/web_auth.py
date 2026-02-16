"""Web auth (non-Bitrix) for portal owner."""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from pydantic import BaseModel, EmailStr

from apps.backend.deps import get_db
from apps.backend.auth import get_password_hash, verify_password, create_portal_token_with_user, decode_token
from apps.backend.models.portal import Portal, PortalUsersAccess
from apps.backend.models.portal_link_request import PortalLinkRequest
from apps.backend.models.portal_kb_setting import PortalKBSetting
from apps.backend.models.portal_telegram_setting import PortalTelegramSetting
from apps.backend.models.portal_bot_flow import PortalBotFlow
from apps.backend.models.kb import KBSource, KBFile, KBChunk, KBJob
from apps.backend.models.web_user import WebUser, WebSession
from apps.backend.services.activity import log_activity
from apps.backend.services.portal_tokens import get_valid_access_token, BitrixAuthError
from apps.backend.clients.bitrix import user_get
from apps.backend.services.telegram_settings import (
    normalize_telegram_username,
    get_portal_telegram_settings,
    set_portal_telegram_settings,
    get_portal_telegram_secret,
    get_portal_telegram_token_plain,
)
from apps.backend.clients.telegram import telegram_get_me, telegram_set_webhook
from apps.backend.config import get_settings
from apps.backend.services.web_email import (
    create_email_token,
    send_registration_email,
    send_registration_confirmed_email,
    get_valid_confirm_token,
)

router = APIRouter()
security = HTTPBearer(auto_error=False)


class RegisterBody(BaseModel):
    email: EmailStr
    password: str
    company: str | None = None


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    session_token: str
    portal_id: int
    portal_token: str
    email: str


class RegisterResponse(BaseModel):
    status: str
    email: str


def _create_web_portal(db: Session, email: str, company: str | None) -> Portal:
    portal = Portal(
        domain=f"web:{uuid4()}",
        status="active",
        install_type="web",
        metadata_json=json.dumps({"owner_email": email, "company": company or ""}, ensure_ascii=False),
    )
    db.add(portal)
    db.commit()
    db.refresh(portal)
    return portal


def _create_session(db: Session, user: WebUser) -> str:
    token = secrets.token_urlsafe(32)
    session = WebSession(
        user_id=user.id,
        token=token,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=30),
    )
    db.add(session)
    db.commit()
    return token


def _get_current_web_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> WebUser:
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = credentials.credentials
    session = db.execute(
        select(WebSession).where(WebSession.token == token)
    ).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=401, detail="Invalid token")
    if session.expires_at and session.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Token expired")
    user = db.get(WebUser, session.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.post("/auth/register", response_model=RegisterResponse)
def register(body: RegisterBody, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="password_too_short")
    existing = db.execute(select(WebUser).where(WebUser.email == email)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="email_exists")
    portal = _create_web_portal(db, email, body.company)
    user = WebUser(
        email=email,
        password_hash=get_password_hash(body.password),
        portal_id=portal.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    portal.admin_user_id = user.id
    db.add(portal)
    db.commit()
    token = create_email_token(db, user.id)
    ok, err = send_registration_email(db, user, token)
    if not ok:
        raise HTTPException(status_code=500, detail=err or "email_send_failed")
    return RegisterResponse(status="confirm_required", email=user.email)


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginBody, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    user = db.execute(select(WebUser).where(WebUser.email == email)).scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid_credentials")
    if not user.email_verified_at:
        raise HTTPException(status_code=403, detail="email_not_verified")
    if not user.portal_id:
        raise HTTPException(status_code=400, detail="missing_portal")
    session_token = _create_session(db, user)
    portal_token = create_portal_token_with_user(user.portal_id, user.id, expires_minutes=60)
    log_activity(db, kind="web", portal_id=user.portal_id, web_user_id=user.id)
    return TokenResponse(
        session_token=session_token,
        portal_id=int(user.portal_id),
        portal_token=portal_token,
        email=user.email,
    )


class ConfirmEmailBody(BaseModel):
    email: EmailStr


@router.get("/auth/confirm")
def confirm_email(token: str, db: Session = Depends(get_db)):
    if not token:
        raise HTTPException(status_code=400, detail="missing_token")
    rec = get_valid_confirm_token(db, token)
    if not rec:
        raise HTTPException(status_code=400, detail="invalid_or_expired_token")
    user = db.get(WebUser, rec.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="user_not_found")
    if not user.email_verified_at:
        user.email_verified_at = datetime.utcnow()
        user.updated_at = datetime.utcnow()
    rec.used_at = datetime.utcnow()
    db.add(user)
    db.add(rec)
    db.commit()
    send_registration_confirmed_email(db, user)
    return {"status": "ok", "email": user.email}


@router.post("/auth/resend-confirm")
def resend_confirm(body: ConfirmEmailBody, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    user = db.execute(select(WebUser).where(WebUser.email == email)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")
    if user.email_verified_at:
        return {"status": "already_verified"}
    token = create_email_token(db, user.id)
    ok, err = send_registration_email(db, user, token)
    if not ok:
        raise HTTPException(status_code=500, detail=err or "email_send_failed")
    return {"status": "ok"}


@router.get("/auth/me", response_model=TokenResponse)
def me(
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    if not user.portal_id:
        raise HTTPException(status_code=400, detail="missing_portal")
    portal_token = create_portal_token_with_user(user.portal_id, user.id, expires_minutes=60)
    log_activity(db, kind="web", portal_id=user.portal_id, web_user_id=user.id)
    return TokenResponse(
        session_token="",
        portal_id=int(user.portal_id),
        portal_token=portal_token,
        email=user.email,
    )


@router.post("/auth/logout")
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
):
    if not credentials:
        return {"status": "ok"}
    token = credentials.credentials
    session = db.execute(select(WebSession).where(WebSession.token == token)).scalar_one_or_none()
    if session:
        db.delete(session)
        db.commit()
    return {"status": "ok"}


class WebUserItem(BaseModel):
    id: str
    name: str
    telegram_username: str | None = None


class CreateWebUserBody(BaseModel):
    name: str
    telegram_username: str | None = None


class LinkRequestItem(BaseModel):
    id: int
    portal_id: int
    portal_domain: str
    status: str
    created_at: datetime


class LinkApproveBody(BaseModel):
    kb_strategy: str = "merge"  # merge|keep_web|keep_bitrix
    bots_strategy: str = "keep_web"  # keep_web|keep_bitrix
    flow_strategy: str = "keep_web"  # keep_web|keep_bitrix


class AccessUserItem(BaseModel):
    user_id: int
    telegram_username: str | None = None


class AccessUsersBody(BaseModel):
    user_ids: list[int] | None = None
    items: list[AccessUserItem] | None = None


class TelegramBotSettingsBody(BaseModel):
    bot_token: str | None = None
    enabled: bool | None = None
    clear_token: bool = False
    allow_uploads: bool | None = None


@router.get("/portals/{portal_id}/users")
def list_web_users(
    portal_id: int,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    if int(user.portal_id or 0) != portal_id:
        raise HTTPException(status_code=403, detail="forbidden")
    rows = db.execute(
        select(PortalUsersAccess).where(PortalUsersAccess.portal_id == portal_id, PortalUsersAccess.kind == "web")
    ).scalars().all()
    items = [
        {"id": r.user_id, "name": r.display_name or "", "telegram_username": r.telegram_username}
        for r in rows
    ]
    return {"items": items}


@router.post("/portals/{portal_id}/users")
def add_web_user(
    portal_id: int,
    body: CreateWebUserBody,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    if int(user.portal_id or 0) != portal_id:
        raise HTTPException(status_code=403, detail="forbidden")
    uid = f"webu_{uuid4().hex[:10]}"
    rec = PortalUsersAccess(
        portal_id=portal_id,
        user_id=uid,
        display_name=body.name.strip(),
        telegram_username=normalize_telegram_username(body.telegram_username),
        kind="web",
    )
    db.add(rec)
    db.commit()
    return {"status": "ok", "id": uid}


@router.delete("/portals/{portal_id}/users/{user_id}")
def delete_web_user(
    portal_id: int,
    user_id: str,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    if int(user.portal_id or 0) != portal_id:
        raise HTTPException(status_code=403, detail="forbidden")
    rec = db.execute(
        select(PortalUsersAccess).where(
            PortalUsersAccess.portal_id == portal_id,
            PortalUsersAccess.user_id == user_id,
            PortalUsersAccess.kind == "web",
        )
    ).scalar_one_or_none()
    if rec:
        db.delete(rec)
        db.commit()
    return {"status": "ok"}


@router.get("/portals/{portal_id}/access/users")
def list_portal_access_users(
    portal_id: int,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    if int(user.portal_id or 0) != portal_id:
        raise HTTPException(status_code=403, detail="forbidden")
    rows = db.execute(
        select(PortalUsersAccess).where(PortalUsersAccess.portal_id == portal_id)
    ).scalars().all()
    items = [{
        "user_id": r.user_id,
        "telegram_username": r.telegram_username,
        "display_name": r.display_name,
        "kind": r.kind,
    } for r in rows]
    user_ids = [r.user_id for r in rows if (r.kind or "bitrix") == "bitrix"]
    return {"user_ids": user_ids, "items": items}


@router.put("/portals/{portal_id}/access/users")
def update_portal_access_users(
    portal_id: int,
    body: AccessUsersBody,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    if int(user.portal_id or 0) != portal_id:
        raise HTTPException(status_code=403, detail="forbidden")
    items = body.items or []
    if not items and body.user_ids:
        items = [AccessUserItem(user_id=int(uid)) for uid in body.user_ids]
    db.execute(delete(PortalUsersAccess).where(
        PortalUsersAccess.portal_id == portal_id,
        PortalUsersAccess.kind == "bitrix",
    ))
    seen_tg: set[str] = set()
    for it in items:
        uname = normalize_telegram_username(it.telegram_username)
        if uname:
            if uname in seen_tg:
                raise HTTPException(status_code=400, detail=f"duplicate_telegram_username:{uname}")
            seen_tg.add(uname)
        db.add(PortalUsersAccess(
            portal_id=portal_id,
            user_id=str(it.user_id),
            telegram_username=uname,
            kind="bitrix",
        ))
    db.commit()
    return {"status": "ok", "count": len(items)}


@router.post("/portals/{portal_id}/bitrix/users/sync")
def sync_bitrix_users(
    portal_id: int,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    if int(user.portal_id or 0) != portal_id:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        access_token = get_valid_access_token(db, portal_id)
    except BitrixAuthError as e:
        raise HTTPException(status_code=400, detail=e.detail)
    portal = db.get(Portal, portal_id)
    if not portal or not portal.domain:
        raise HTTPException(status_code=404, detail="portal_not_found")
    domain_full = f"https://{portal.domain}"
    users_list, err = user_get(domain_full, access_token, start=0, limit=200)
    if err == "missing_scope_user":
        raise HTTPException(status_code=403, detail="missing_scope_user")
    if err:
        raise HTTPException(status_code=502, detail=err)
    existing = db.execute(
        select(PortalUsersAccess).where(
            PortalUsersAccess.portal_id == portal_id,
            PortalUsersAccess.kind == "bitrix",
        )
    ).scalars().all()
    existing_map = {r.user_id: r for r in existing}
    for u in users_list:
        uid = str(u.get("ID"))
        if not uid or uid == "None":
            continue
        name = (u.get("NAME") or "") + " " + (u.get("LAST_NAME") or "")
        name = name.strip() or (u.get("EMAIL") or "")
        if uid in existing_map:
            row = existing_map[uid]
            if name:
                row.display_name = name
            db.add(row)
        else:
            db.add(PortalUsersAccess(
                portal_id=portal_id,
                user_id=uid,
                display_name=name,
                kind="bitrix",
            ))
    db.commit()
    return {"status": "ok", "count": len(users_list)}


@router.get("/portals/{portal_id}/telegram/staff")
def get_web_telegram_staff_settings(
    portal_id: int,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    if int(user.portal_id or 0) != portal_id:
        raise HTTPException(status_code=403, detail="forbidden")
    settings = get_portal_telegram_settings(db, portal_id)
    secret = get_portal_telegram_secret(db, portal_id, "staff") or ""
    webhook_url = _telegram_webhook_url("staff", portal_id, secret) if secret else None
    return {"kind": "staff", **settings.get("staff", {}), "webhook_url": webhook_url}


@router.post("/portals/{portal_id}/telegram/staff")
def set_web_telegram_staff_settings(
    portal_id: int,
    body: TelegramBotSettingsBody,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    if int(user.portal_id or 0) != portal_id:
        raise HTTPException(status_code=403, detail="forbidden")
    if body.clear_token:
        body.enabled = False
    settings = set_portal_telegram_settings(
        db,
        portal_id,
        kind="staff",
        bot_token=body.bot_token,
        enabled=body.enabled,
        clear_token=bool(body.clear_token),
        allow_uploads=body.allow_uploads,
    )
    secret = get_portal_telegram_secret(db, portal_id, "staff") or ""
    webhook_url = _telegram_webhook_url("staff", portal_id, secret) if secret else None
    webhook_ok = None
    webhook_error = None
    bot_info = None
    if settings.get("staff", {}).get("enabled") and not webhook_url:
        webhook_error = "missing_public_base_url"
    if webhook_url and settings.get("staff", {}).get("has_token") and settings.get("staff", {}).get("enabled"):
        token_plain = body.bot_token or (get_portal_telegram_token_plain(db, portal_id, "staff") or "")
        if token_plain:
            bot_info, _ = telegram_get_me(token_plain)
            webhook_ok, webhook_error = telegram_set_webhook(token_plain, webhook_url, secret)
    return {
        "kind": "staff",
        **settings.get("staff", {}),
        "webhook_url": webhook_url,
        "webhook_ok": webhook_ok,
        "webhook_error": webhook_error,
        "bot_username": bot_info.get("username") if bot_info else None,
        "bot_id": bot_info.get("id") if bot_info else None,
    }


@router.get("/portals/{portal_id}/telegram/client")
def get_web_telegram_client_settings(
    portal_id: int,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    if int(user.portal_id or 0) != portal_id:
        raise HTTPException(status_code=403, detail="forbidden")
    settings = get_portal_telegram_settings(db, portal_id)
    secret = get_portal_telegram_secret(db, portal_id, "client") or ""
    webhook_url = _telegram_webhook_url("client", portal_id, secret) if secret else None
    return {"kind": "client", **settings.get("client", {}), "webhook_url": webhook_url}


@router.post("/portals/{portal_id}/telegram/client")
def set_web_telegram_client_settings(
    portal_id: int,
    body: TelegramBotSettingsBody,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    if int(user.portal_id or 0) != portal_id:
        raise HTTPException(status_code=403, detail="forbidden")
    if body.clear_token:
        body.enabled = False
    settings = set_portal_telegram_settings(
        db,
        portal_id,
        kind="client",
        bot_token=body.bot_token,
        enabled=body.enabled,
        clear_token=bool(body.clear_token),
        allow_uploads=body.allow_uploads,
    )
    secret = get_portal_telegram_secret(db, portal_id, "client") or ""
    webhook_url = _telegram_webhook_url("client", portal_id, secret) if secret else None
    webhook_ok = None
    webhook_error = None
    bot_info = None
    if settings.get("client", {}).get("enabled") and not webhook_url:
        webhook_error = "missing_public_base_url"
    if webhook_url and settings.get("client", {}).get("has_token") and settings.get("client", {}).get("enabled"):
        token_plain = body.bot_token or (get_portal_telegram_token_plain(db, portal_id, "client") or "")
        if token_plain:
            bot_info, _ = telegram_get_me(token_plain)
            webhook_ok, webhook_error = telegram_set_webhook(token_plain, webhook_url, secret)
    return {
        "kind": "client",
        **settings.get("client", {}),
        "webhook_url": webhook_url,
        "webhook_ok": webhook_ok,
        "webhook_error": webhook_error,
        "bot_username": bot_info.get("username") if bot_info else None,
        "bot_id": bot_info.get("id") if bot_info else None,
    }


def _merge_kb(db: Session, source_portal_id: int, target_portal_id: int, strategy: str):
    if strategy == "keep_bitrix":
        return
    if strategy == "keep_web":
        db.execute(delete(KBChunk).where(KBChunk.portal_id == target_portal_id))
        db.execute(delete(KBFile).where(KBFile.portal_id == target_portal_id))
        db.execute(delete(KBSource).where(KBSource.portal_id == target_portal_id))
        db.execute(delete(KBJob).where(KBJob.portal_id == target_portal_id))
    db.execute(update(KBSource).where(KBSource.portal_id == source_portal_id).values(portal_id=target_portal_id))
    db.execute(update(KBFile).where(KBFile.portal_id == source_portal_id).values(portal_id=target_portal_id))
    db.execute(update(KBChunk).where(KBChunk.portal_id == source_portal_id).values(portal_id=target_portal_id))
    db.execute(update(KBJob).where(KBJob.portal_id == source_portal_id).values(portal_id=target_portal_id))


def _merge_kb_settings(db: Session, source_portal_id: int, target_portal_id: int, strategy: str):
    if strategy == "keep_bitrix":
        return
    source = db.get(PortalKBSetting, source_portal_id)
    if not source:
        return
    if strategy == "merge":
        target = db.get(PortalKBSetting, target_portal_id)
        if target:
            return
    db.execute(delete(PortalKBSetting).where(PortalKBSetting.portal_id == target_portal_id))
    clone = PortalKBSetting(
        portal_id=target_portal_id,
        embedding_model=source.embedding_model,
        chat_model=source.chat_model,
        api_base=source.api_base,
        prompt_preset=source.prompt_preset,
        temperature=source.temperature,
        max_tokens=source.max_tokens,
        top_p=source.top_p,
        presence_penalty=source.presence_penalty,
        frequency_penalty=source.frequency_penalty,
        allow_general=source.allow_general,
        strict_mode=source.strict_mode,
        context_messages=source.context_messages,
        context_chars=source.context_chars,
        retrieval_top_k=source.retrieval_top_k,
        retrieval_max_chars=source.retrieval_max_chars,
        lex_boost=source.lex_boost,
        use_history=source.use_history,
        use_cache=source.use_cache,
        system_prompt_extra=source.system_prompt_extra,
        updated_at=source.updated_at,
    )
    db.add(clone)


def _merge_telegram(db: Session, source_portal_id: int, target_portal_id: int, strategy: str):
    if strategy == "keep_bitrix":
        return
    source = db.get(PortalTelegramSetting, source_portal_id)
    if not source:
        return
    db.execute(delete(PortalTelegramSetting).where(PortalTelegramSetting.portal_id == target_portal_id))
    clone = PortalTelegramSetting(
        portal_id=target_portal_id,
        staff_bot_token_enc=source.staff_bot_token_enc,
        staff_bot_secret=source.staff_bot_secret,
        staff_bot_enabled=source.staff_bot_enabled,
        client_bot_token_enc=source.client_bot_token_enc,
        client_bot_secret=source.client_bot_secret,
        client_bot_enabled=source.client_bot_enabled,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )
    db.add(clone)


def _merge_flow(db: Session, source_portal_id: int, target_portal_id: int, strategy: str):
    if strategy == "keep_bitrix":
        return
    rows = db.execute(
        select(PortalBotFlow).where(PortalBotFlow.portal_id == source_portal_id)
    ).scalars().all()
    if not rows:
        return
    db.execute(delete(PortalBotFlow).where(PortalBotFlow.portal_id == target_portal_id))
    for row in rows:
        clone = PortalBotFlow(
            portal_id=target_portal_id,
            kind=row.kind,
            draft_json=row.draft_json,
            published_json=row.published_json,
            updated_at=row.updated_at,
        )
        db.add(clone)


def _merge_web_access(db: Session, source_portal_id: int, target_portal_id: int):
    db.execute(
        update(PortalUsersAccess)
        .where(
            PortalUsersAccess.portal_id == source_portal_id,
            PortalUsersAccess.kind == "web",
        )
        .values(portal_id=target_portal_id)
    )


def _telegram_webhook_url(kind: str, portal_id: int, secret: str) -> str | None:
    s = get_settings()
    base = (s.public_base_url or "").rstrip("/")
    if not base:
        return None
    return f"{base}/v1/telegram/{kind}/{portal_id}/{secret}"


@router.get("/link/requests")
def list_link_requests(
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(PortalLinkRequest).where(PortalLinkRequest.web_user_id == user.id).order_by(PortalLinkRequest.created_at.desc())
    ).scalars().all()
    items = []
    for r in rows:
        portal = db.get(Portal, r.portal_id)
        if not portal:
            continue
        items.append({
            "id": r.id,
            "portal_id": r.portal_id,
            "portal_domain": portal.domain,
            "status": r.status,
            "created_at": r.created_at,
        })
    return {"items": items}


@router.post("/link/requests/{request_id}/approve")
def approve_link_request(
    request_id: int,
    body: LinkApproveBody,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    req = db.get(PortalLinkRequest, request_id)
    if not req or req.web_user_id != user.id:
        raise HTTPException(status_code=404, detail="not_found")
    if req.status != "pending":
        return {"status": req.status}
    source_portal_id = req.source_portal_id or user.portal_id
    target_portal_id = req.portal_id
    if not source_portal_id or not target_portal_id:
        raise HTTPException(status_code=400, detail="missing_portal")
    if source_portal_id != target_portal_id:
        _merge_kb(db, source_portal_id, target_portal_id, body.kb_strategy)
        _merge_kb_settings(db, source_portal_id, target_portal_id, body.kb_strategy)
        _merge_telegram(db, source_portal_id, target_portal_id, body.bots_strategy)
        _merge_flow(db, source_portal_id, target_portal_id, body.flow_strategy)
        _merge_web_access(db, source_portal_id, target_portal_id)
    user.portal_id = target_portal_id
    db.add(user)
    req.status = "approved"
    req.merge_json = json.dumps(body.dict(), ensure_ascii=False)
    db.add(req)
    db.commit()
    return {"status": "approved"}


@router.post("/link/requests/{request_id}/reject")
def reject_link_request(
    request_id: int,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    req = db.get(PortalLinkRequest, request_id)
    if not req or req.web_user_id != user.id:
        raise HTTPException(status_code=404, detail="not_found")
    if req.status != "pending":
        return {"status": req.status}
    req.status = "rejected"
    db.add(req)
    db.commit()
    return {"status": "rejected"}
