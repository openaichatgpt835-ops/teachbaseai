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
from apps.backend.models.account import AppSession, AppUserWebCredential, AccountMembership, Account, AccountIntegration
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
    get_valid_email_token,
    send_password_reset_email,
)
from apps.backend.services.identity_linking import link_or_create_app_user
from apps.backend.services.rbac_service import ensure_rbac_for_web_user, get_account_id_by_portal_id, ensure_account_member
from apps.backend.services.billing import get_portal_effective_policy

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
    active_account_id: int | None = None
    accounts: list[dict] | None = None


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


def _create_bridge_session(
    db: Session,
    *,
    web_user: WebUser,
    app_user_id: int,
    active_account_id: int | None,
) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=30)
    db.add(
        WebSession(
            user_id=int(web_user.id),
            app_user_id=int(app_user_id),
            token=token,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
        )
    )
    db.add(
        AppSession(
            user_id=int(app_user_id),
            active_account_id=int(active_account_id) if active_account_id else None,
            token=token,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
        )
    )
    db.commit()
    return token


def _get_app_session_by_token(db: Session, token: str) -> AppSession | None:
    return db.execute(select(AppSession).where(AppSession.token == token)).scalar_one_or_none()


def _resolve_primary_portal(db: Session, account_id: int) -> Portal | None:
    rows = db.execute(
        select(Portal)
        .where(Portal.account_id == account_id)
        .order_by(
            Portal.install_type.asc(),
            Portal.id.asc(),
        )
    ).scalars().all()
    if not rows:
        return None
    bitrix = [p for p in rows if "bitrix24." in (p.domain or "").lower()]
    web = [p for p in rows if (p.install_type or "").lower() == "web" or (p.domain or "").lower().startswith("web:")]
    return (bitrix[0] if bitrix else (web[0] if web else rows[0]))


def _ensure_bridge_web_user(
    db: Session,
    *,
    email: str,
    password_hash: str,
    portal_id: int | None,
    email_verified_at: datetime | None,
) -> WebUser:
    now = datetime.utcnow()
    user = db.execute(select(WebUser).where(WebUser.email == email)).scalar_one_or_none()
    if not user:
        user = WebUser(
            email=email,
            password_hash=password_hash,
            portal_id=portal_id,
            email_verified_at=email_verified_at,
            created_at=now,
            updated_at=now,
        )
        db.add(user)
        db.flush()
        return user
    user.password_hash = password_hash
    user.portal_id = portal_id
    if email_verified_at and not user.email_verified_at:
        user.email_verified_at = email_verified_at
    user.updated_at = now
    db.add(user)
    db.flush()
    return user


def _list_active_accounts(db: Session, app_user_id: int) -> list[dict]:
    rows = db.execute(
        select(AccountMembership, Account)
        .join(Account, Account.id == AccountMembership.account_id)
        .where(
            AccountMembership.user_id == app_user_id,
            AccountMembership.status.in_(["active", "invited"]),
        )
        .order_by(AccountMembership.role.desc(), Account.id.asc())
    ).all()
    items: list[dict] = []
    seen: set[int] = set()
    for membership, account in rows:
        if int(account.id) in seen:
            continue
        seen.add(int(account.id))
        items.append(
            {
                "id": int(account.id),
                "account_no": int(account.account_no) if account.account_no is not None else None,
                "name": account.name,
                "slug": account.slug,
                "role": membership.role,
                "status": membership.status,
            }
        )
    return items


def _pick_active_account_id(
    db: Session,
    *,
    app_user_id: int,
    email: str,
) -> int | None:
    memberships = db.execute(
        select(AccountMembership.account_id, AccountMembership.role)
        .where(
            AccountMembership.user_id == app_user_id,
            AccountMembership.status.in_(["active", "invited"]),
        )
        .order_by(AccountMembership.role.desc(), AccountMembership.account_id.asc())
    ).all()
    if not memberships:
        return None
    web_user = db.execute(select(WebUser).where(WebUser.email == email)).scalar_one_or_none()
    if web_user and web_user.portal_id:
        portal = db.get(Portal, int(web_user.portal_id))
        if portal and portal.account_id:
            return int(portal.account_id)
    return int(memberships[0][0])


def _build_token_response(
    db: Session,
    *,
    session_token: str,
    email: str,
    app_user_id: int,
    active_account_id: int | None,
    bridge_user: WebUser,
) -> TokenResponse:
    portal_id = int(bridge_user.portal_id or 0)
    portal_token = create_portal_token_with_user(portal_id, bridge_user.id if portal_id else None, expires_minutes=60) if portal_id else ""
    return TokenResponse(
        session_token=session_token,
        portal_id=portal_id,
        portal_token=portal_token,
        email=email,
        active_account_id=int(active_account_id) if active_account_id else None,
        accounts=_list_active_accounts(db, int(app_user_id)),
    )


def _get_current_web_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> WebSession:
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
    return session


def _get_current_web_user(
    session: WebSession = Depends(_get_current_web_session),
    db: Session = Depends(get_db),
) -> WebUser:
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
    ensure_rbac_for_web_user(db, user, force_owner=True, account_name=(body.company or "").strip() or None)
    db.commit()
    token = create_email_token(db, user.id)
    ok, err = send_registration_email(db, user, token)
    if not ok:
        raise HTTPException(status_code=500, detail=err or "email_send_failed")
    return RegisterResponse(status="confirm_required", email=user.email)


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginBody, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    cred = db.execute(select(AppUserWebCredential).where(AppUserWebCredential.email == email)).scalar_one_or_none()
    legacy_user = db.execute(select(WebUser).where(WebUser.email == email)).scalar_one_or_none()
    if cred:
        if not verify_password(body.password, cred.password_hash):
            raise HTTPException(status_code=401, detail="invalid_credentials")
        if not cred.email_verified_at:
            raise HTTPException(status_code=403, detail="email_not_verified")
        app_user_id = int(cred.user_id)
        active_account_id = _pick_active_account_id(db, app_user_id=app_user_id, email=email)
        if active_account_id is None:
            raise HTTPException(status_code=400, detail="missing_account")
        primary_portal = _resolve_primary_portal(db, int(active_account_id))
        bridge_user = _ensure_bridge_web_user(
            db,
            email=email,
            password_hash=cred.password_hash,
            portal_id=int(primary_portal.id) if primary_portal else None,
            email_verified_at=cred.email_verified_at,
        )
        db.execute(delete(WebSession).where(WebSession.user_id == bridge_user.id))
        db.execute(delete(AppSession).where(AppSession.user_id == app_user_id))
        db.commit()
        session_token = _create_bridge_session(
            db,
            web_user=bridge_user,
            app_user_id=app_user_id,
            active_account_id=active_account_id,
        )
        log_activity(db, kind="web", portal_id=bridge_user.portal_id, web_user_id=bridge_user.id)
        return _build_token_response(
            db,
            session_token=session_token,
            email=email,
            app_user_id=app_user_id,
            active_account_id=active_account_id,
            bridge_user=bridge_user,
        )
    user = legacy_user
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid_credentials")
    if not user.email_verified_at:
        raise HTTPException(status_code=403, detail="email_not_verified")
    if not user.portal_id:
        raise HTTPException(status_code=400, detail="missing_portal")
    ensure_rbac_for_web_user(db, user)
    db.commit()
    cred = db.execute(select(AppUserWebCredential).where(AppUserWebCredential.email == email)).scalar_one_or_none()
    app_user_id = int(cred.user_id) if cred else None
    active_account_id = get_account_id_by_portal_id(db, int(user.portal_id))
    if app_user_id:
        primary_portal = _resolve_primary_portal(db, int(active_account_id)) if active_account_id else None
        bridge_user = _ensure_bridge_web_user(
            db,
            email=email,
            password_hash=cred.password_hash,
            portal_id=int(primary_portal.id) if primary_portal else int(user.portal_id),
            email_verified_at=cred.email_verified_at or user.email_verified_at,
        )
        db.execute(delete(AppSession).where(AppSession.user_id == app_user_id))
        db.execute(delete(WebSession).where(WebSession.user_id == bridge_user.id))
        db.commit()
        session_token = _create_bridge_session(
            db,
            web_user=bridge_user,
            app_user_id=app_user_id,
            active_account_id=active_account_id,
        )
        user = bridge_user
    else:
        session_token = _create_session(db, user)
    log_activity(db, kind="web", portal_id=user.portal_id, web_user_id=user.id)
    return _build_token_response(
        db,
        session_token=session_token,
        email=user.email,
        app_user_id=int(app_user_id or 0),
        active_account_id=active_account_id,
        bridge_user=user,
    )


class ConfirmEmailBody(BaseModel):
    email: EmailStr


class ForgotPasswordBody(BaseModel):
    email: EmailStr


class ResetPasswordBody(BaseModel):
    token: str
    password: str


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


@router.post("/auth/password/forgot")
def forgot_password(body: ForgotPasswordBody, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    user = db.execute(select(WebUser).where(WebUser.email == email)).scalar_one_or_none()
    if not user:
        return {"status": "ok"}
    token = create_email_token(
        db,
        user.id,
        kind="reset_password",
        expires_in=timedelta(hours=2),
    )
    ok, err = send_password_reset_email(db, user, token)
    if not ok:
        raise HTTPException(status_code=500, detail=err or "email_send_failed")
    return {"status": "ok"}


@router.post("/auth/password/reset")
def reset_password(body: ResetPasswordBody, db: Session = Depends(get_db)):
    token = (body.token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="missing_token")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="password_too_short")
    rec = get_valid_email_token(db, token, kind="reset_password")
    if not rec:
        raise HTTPException(status_code=400, detail="invalid_or_expired_token")
    user = db.get(WebUser, rec.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="user_not_found")
    new_hash = get_password_hash(body.password)
    user.password_hash = new_hash
    user.updated_at = datetime.utcnow()
    rec.used_at = datetime.utcnow()
    db.execute(delete(WebSession).where(WebSession.user_id == user.id))
    db.add(user)
    db.add(rec)
    cred = db.execute(
        select(AppUserWebCredential).where(AppUserWebCredential.email == user.email)
    ).scalar_one_or_none()
    if cred:
        cred.password_hash = new_hash
        cred.must_change_password = False
        cred.updated_at = datetime.utcnow()
        db.add(cred)
    db.commit()
    return {"status": "ok"}


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
    session: WebSession = Depends(_get_current_web_session),
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    if not user.portal_id:
        raise HTTPException(status_code=400, detail="missing_portal")
    ensure_rbac_for_web_user(db, user)
    db.commit()
    creds = db.execute(select(AppUserWebCredential).where(AppUserWebCredential.email == user.email)).scalar_one_or_none()
    app_user_id = int(session.app_user_id or 0)
    if creds and not app_user_id:
        app_user_id = int(creds.user_id)
        session.app_user_id = app_user_id
        db.add(session)
        db.commit()
    app_session = _get_app_session_by_token(db, session.token)
    active_account_id = int(app_session.active_account_id) if app_session and app_session.active_account_id else None
    if active_account_id is None and user.portal_id:
        active_account_id = get_account_id_by_portal_id(db, int(user.portal_id))
    log_activity(db, kind="web", portal_id=user.portal_id, web_user_id=user.id)
    return _build_token_response(
        db,
        session_token=session.token,
        email=user.email,
        app_user_id=app_user_id,
        active_account_id=active_account_id,
        bridge_user=user,
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
    app_session = _get_app_session_by_token(db, token)
    if app_session:
        db.delete(app_session)
    db.commit()
    return {"status": "ok"}


class SwitchAccountBody(BaseModel):
    account_id: int


@router.post("/auth/switch-account", response_model=TokenResponse)
def switch_account(
    body: SwitchAccountBody,
    session: WebSession = Depends(_get_current_web_session),
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    target_account = db.execute(
        select(AccountMembership.account_id)
        .where(
            AccountMembership.user_id == int(session.app_user_id or 0),
            AccountMembership.account_id == int(body.account_id),
            AccountMembership.status.in_(["active", "invited"]),
        )
    ).scalar_one_or_none()
    if not target_account:
        raise HTTPException(status_code=403, detail="forbidden")
    app_session = _get_app_session_by_token(db, session.token)
    if not app_session:
        raise HTTPException(status_code=401, detail="Invalid token")
    app_session.active_account_id = int(body.account_id)
    primary_portal = _resolve_primary_portal(db, int(body.account_id))
    user.portal_id = int(primary_portal.id) if primary_portal else None
    user.updated_at = datetime.utcnow()
    db.add(app_session)
    db.add(user)
    db.commit()
    return _build_token_response(
        db,
        session_token=session.token,
        email=user.email,
        app_user_id=int(session.app_user_id or 0),
        active_account_id=int(body.account_id),
        bridge_user=user,
    )


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
    account_id, _app_user_id = ensure_rbac_for_web_user(db, user)
    if not account_id:
        raise HTTPException(status_code=400, detail="missing_account")
    integ = db.execute(
        select(AccountIntegration).where(
            AccountIntegration.account_id == int(account_id),
            AccountIntegration.provider == "bitrix",
            AccountIntegration.portal_id == int(portal_id),
        )
    ).scalar_one_or_none()
    if not integ:
        integ = db.execute(
            select(AccountIntegration).where(
                AccountIntegration.provider == "bitrix",
                AccountIntegration.external_key == str(portal.domain or "").strip().lower(),
            )
        ).scalar_one_or_none()
    if not integ:
        integ = AccountIntegration(
            account_id=int(account_id),
            provider="bitrix",
            status="active",
            external_key=str(portal.domain or "").strip().lower(),
            portal_id=int(portal_id),
            credentials_json=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(integ)
        db.flush()
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
    linked_count = 0
    membership_created_count = 0
    skipped_count = 0
    skipped_examples: list[dict[str, str]] = []
    for u in users_list:
        uid = str(u.get("ID"))
        if not uid or uid == "None":
            continue
        name = (u.get("NAME") or "") + " " + (u.get("LAST_NAME") or "")
        name = name.strip() or (u.get("EMAIL") or "")
        email = (str(u.get("EMAIL") or "").strip().lower() or None)
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
        link_result = link_or_create_app_user(
            db,
            provider="bitrix",
            integration_id=int(integ.id),
            external_id=uid,
            display_value=name or email or f"Bitrix user {uid}",
            email=email,
            auto_create_user=True,
            meta_json={
                "email": email,
                "name": (u.get("NAME") or None),
                "last_name": (u.get("LAST_NAME") or None),
                "portal_id": int(portal_id),
            },
        )
        if link_result.user_id:
            _membership, created = ensure_account_member(
                db,
                account_id=int(account_id),
                user_id=int(link_result.user_id),
                role="member",
                status="active",
                kb_access="none",
                can_invite_users=False,
                can_manage_settings=False,
                can_view_finance=False,
            )
            linked_count += 1
            membership_created_count += 1 if created else 0
        else:
            skipped_count += 1
            if len(skipped_examples) < 10:
                skipped_examples.append(
                    {
                        "external_id": uid,
                        "email": email or "",
                        "reason": link_result.reason or link_result.status,
                    }
                )
    db.commit()
    return {
        "status": "ok",
        "count": len(users_list),
        "identity_linking": {
            "linked": linked_count,
            "memberships_created": membership_created_count,
            "skipped": skipped_count,
            "examples": skipped_examples,
        },
    }


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
    policy = get_portal_effective_policy(db, portal_id)
    if not bool((policy.get("features") or {}).get("allow_client_bot", True)):
        raise HTTPException(status_code=403, detail="client_bot_locked")
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
