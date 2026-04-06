"""Web RBAC v2 endpoints (account-root user/role/invite management)."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from apps.backend.deps import get_db
from apps.backend.models.account import (
    Account,
    AccountInvite,
    AccountIntegration,
    AccountMembership,
    AccountPermission,
    AccountUserGroup,
    AccountUserGroupMember,
    AppSession,
    AppUser,
    AppUserIdentity,
    AppUserWebCredential,
)
from apps.backend.models.web_user import WebSession, WebUser
from apps.backend.models.portal import Portal, PortalUsersAccess
from apps.backend.services.web_email import build_invite_accept_url, send_account_invite_email
from apps.backend.services.telegram_settings import normalize_telegram_username
from apps.backend.services.billing import (
    get_account_effective_policy,
    get_account_subscription_payload,
    get_account_usage_summary,
    is_account_user_limit_reached,
    list_billing_plans,
)
from apps.backend.services.kb_acl import normalize_kb_access_level
from apps.backend.services.rbac_service import (
    get_account_id_by_portal_id,
    get_membership_ctx,
    require_invite_permission,
    require_membership_ctx,
    require_settings_permission,
)

router = APIRouter()
security = HTTPBearer(auto_error=False)

_ROLE_DEFAULTS: dict[str, dict[str, object]] = {
    "owner": {
        "kb_access": "manage",
        "can_invite_users": True,
        "can_manage_settings": True,
        "can_view_finance": True,
    },
    "admin": {
        "kb_access": "edit",
        "can_invite_users": True,
        "can_manage_settings": True,
        "can_view_finance": True,
    },
    "member": {
        "kb_access": "read",
        "can_invite_users": False,
        "can_manage_settings": False,
        "can_view_finance": False,
    },
    "client": {
        "kb_access": "none",
        "can_invite_users": False,
        "can_manage_settings": False,
        "can_view_finance": False,
    },
}


def _hash_password(password: str) -> str:
    pw = (password or "").encode("utf-8")
    if len(pw) > 72:
        pw = pw[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode()


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


class InviteEmailBody(BaseModel):
    email: EmailStr
    role: str = "member"  # owner|admin|member|client
    kb_access: str | None = None  # none|read|upload|edit|manage
    can_invite_users: bool | None = None
    can_manage_settings: bool | None = None
    can_view_finance: bool | None = None
    expires_days: int = 7


class ManualUserBody(BaseModel):
    display_name: str | None = None
    login: str
    email: EmailStr | None = None
    password: str
    role: str = "member"
    kb_access: str | None = None
    can_invite_users: bool | None = None
    can_manage_settings: bool | None = None
    can_view_finance: bool | None = None


class UpdateUserBody(BaseModel):
    display_name: str | None = None
    role: str | None = None
    status: str | None = None
    kb_access: str | None = None
    can_invite_users: bool | None = None
    can_manage_settings: bool | None = None
    can_view_finance: bool | None = None


class UpdateMembershipPermissionsBody(BaseModel):
    role: str | None = None
    status: str | None = None
    kb_access: str | None = None
    can_invite_users: bool | None = None
    can_manage_settings: bool | None = None
    can_view_finance: bool | None = None


class UpdateTelegramIdentityBody(BaseModel):
    telegram_username: str | None = None


class AcceptInviteBody(BaseModel):
    login: str
    password: str
    display_name: str | None = None
    email: EmailStr | None = None


class AccountUserGroupBody(BaseModel):
    name: str
    kind: str = "staff"
    membership_ids: list[int] = []


def _normalize_role(role: str | None, *, allow_owner: bool = False) -> str:
    value = (role or "member").strip().lower()
    allowed = {"admin", "member", "client"} | ({"owner"} if allow_owner else set())
    if value not in allowed:
        raise HTTPException(status_code=400, detail="invalid_role")
    return value


def _normalize_kb_access(v: str | None) -> str | None:
    if v is None:
        return None
    try:
        vv = normalize_kb_access_level(v, strict=True)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_kb_access")
    return vv


def _normalize_membership_status(v: str | None) -> str | None:
    if v is None:
        return None
    vv = v.strip().lower()
    if vv not in {"active", "invited", "blocked", "deleted"}:
        raise HTTPException(status_code=400, detail="invalid_membership_status")
    return vv


def _normalize_group_kind(v: str | None) -> str:
    value = str(v or "staff").strip().lower()
    if value not in {"staff", "client"}:
        raise HTTPException(status_code=400, detail="invalid_group_kind")
    return value


def _build_permissions(role: str, body: object) -> dict[str, object]:
    d = dict(_ROLE_DEFAULTS.get(role, _ROLE_DEFAULTS["member"]))
    kb_access = _normalize_kb_access(getattr(body, "kb_access", None))
    if kb_access is not None:
        d["kb_access"] = kb_access
    for f in ("can_invite_users", "can_manage_settings", "can_view_finance"):
        val = getattr(body, f, None)
        if val is not None:
            d[f] = bool(val)
    return d


def _upsert_permissions(db: Session, membership_id: int, values: dict[str, object]) -> AccountPermission:
    perm = db.execute(
        select(AccountPermission).where(AccountPermission.membership_id == membership_id)
    ).scalar_one_or_none()
    if not perm:
        perm = AccountPermission(
            membership_id=membership_id,
            kb_access=str(values["kb_access"]),
            can_invite_users=bool(values["can_invite_users"]),
            can_manage_settings=bool(values["can_manage_settings"]),
            can_view_finance=bool(values["can_view_finance"]),
            updated_at=datetime.utcnow(),
        )
        db.add(perm)
    else:
        perm.kb_access = str(values["kb_access"])
        perm.can_invite_users = bool(values["can_invite_users"])
        perm.can_manage_settings = bool(values["can_manage_settings"])
        perm.can_view_finance = bool(values["can_view_finance"])
        perm.updated_at = datetime.utcnow()
    return perm


def _membership_by_account_user(db: Session, account_id: int, user_id: int) -> AccountMembership | None:
    return db.execute(
        select(AccountMembership).where(
            AccountMembership.account_id == account_id,
            AccountMembership.user_id == user_id,
        )
    ).scalar_one_or_none()


def _credential_by_login_or_email(
    db: Session,
    login: str | None = None,
    email: str | None = None,
) -> AppUserWebCredential | None:
    if login:
        row = db.execute(
            select(AppUserWebCredential).where(AppUserWebCredential.login == login.strip().lower())
        ).scalar_one_or_none()
        if row:
            return row
    if email:
        row = db.execute(
            select(AppUserWebCredential).where(AppUserWebCredential.email == email.strip().lower())
        ).scalar_one_or_none()
        if row:
            return row
    return None


def _resolve_account_portal_id(db: Session, account_id: int) -> int | None:
    row = db.execute(
        select(Portal.id).where(Portal.account_id == account_id).order_by(Portal.id.asc())
    ).first()
    if not row:
        return None
    return int(row[0])


def _sync_account_bridge_portal(db: Session, account_id: int, portal_id: int | None) -> None:
    rows = db.execute(
        select(AppUserWebCredential.email)
        .join(AccountMembership, AccountMembership.user_id == AppUserWebCredential.user_id)
        .where(AccountMembership.account_id == int(account_id))
        .where(AccountMembership.status.in_(["active", "invited"]))
        .where(AppUserWebCredential.email.is_not(None))
    ).all()
    emails = [str(row[0]).strip().lower() for row in rows if row and row[0]]
    if not emails:
        return
    rows = db.execute(select(WebUser).where(WebUser.email.in_(emails))).scalars().all()
    now = datetime.utcnow()
    for row in rows:
        row.portal_id = int(portal_id) if portal_id else None
        row.updated_at = now
        db.add(row)


def _list_bitrix_integrations(db: Session, account_id: int) -> list[dict]:
    rows = db.execute(
        select(AccountIntegration, Portal)
        .join(Portal, Portal.id == AccountIntegration.portal_id, isouter=True)
        .where(AccountIntegration.account_id == int(account_id))
        .where(AccountIntegration.provider == "bitrix")
        .order_by(AccountIntegration.id.asc())
    ).all()
    items: list[dict] = []
    for integration, portal in rows:
        meta = dict(integration.credentials_json or {})
        items.append(
            {
                "id": int(integration.id),
                "status": integration.status,
                "external_key": integration.external_key,
                "portal_id": int(integration.portal_id) if integration.portal_id else None,
                "portal_domain": portal.domain if portal else None,
                "install_type": portal.install_type if portal else None,
                "is_primary": bool(meta.get("is_primary")),
                "created_at": integration.created_at.isoformat() if integration.created_at else None,
            }
        )
    return items


def _build_account_users_items(db: Session, account_id: int) -> list[dict]:
    memberships = db.execute(
        select(AccountMembership).where(
            AccountMembership.account_id == account_id,
            AccountMembership.status.in_(["active", "invited"]),
        )
    ).scalars().all()
    if not memberships:
        return []

    user_ids = [int(m.user_id) for m in memberships]
    membership_ids = [int(m.id) for m in memberships]
    users = db.execute(select(AppUser).where(AppUser.id.in_(user_ids))).scalars().all()
    creds = db.execute(
        select(AppUserWebCredential).where(AppUserWebCredential.user_id.in_(user_ids))
    ).scalars().all()
    perms = db.execute(
        select(AccountPermission).where(AccountPermission.membership_id.in_(membership_ids))
    ).scalars().all()
    identities = db.execute(
        select(AppUserIdentity).where(AppUserIdentity.user_id.in_(user_ids))
    ).scalars().all()
    integrations = db.execute(
        select(AccountIntegration).where(AccountIntegration.account_id == account_id)
    ).scalars().all()
    integration_ids_by_provider: dict[str, set[int]] = {}
    for integration in integrations:
        provider = (integration.provider or "").strip().lower()
        if not provider:
            continue
        integration_ids_by_provider.setdefault(provider, set()).add(int(integration.id))
    portal_id = _resolve_account_portal_id(db, account_id)
    portal_bitrix_external_ids: set[str] = set()
    if portal_id:
        portal_bitrix_external_ids = {
            str(row.user_id).strip()
            for row in db.execute(
                select(PortalUsersAccess).where(
                    PortalUsersAccess.portal_id == int(portal_id),
                    PortalUsersAccess.kind == "bitrix",
                )
            ).scalars().all()
            if str(row.user_id).strip()
        }

    users_by_id = {int(u.id): u for u in users}
    creds_by_user = {int(c.user_id): c for c in creds}
    perms_by_membership = {int(p.membership_id): p for p in perms}
    ids_by_user: dict[int, list[AppUserIdentity]] = {}
    for ident in identities:
        ids_by_user.setdefault(int(ident.user_id), []).append(ident)

    items = []
    for m in memberships:
        uid = int(m.user_id)
        u = users_by_id.get(uid)
        c = creds_by_user.get(uid)
        p = perms_by_membership.get(int(m.id))
        idents = ids_by_user.get(uid, [])
        def _identity_visible(x: AppUserIdentity) -> bool:
            provider = (x.provider or "").strip().lower()
            scoped = integration_ids_by_provider.get(provider, set())
            if x.integration_id is not None:
                return int(x.integration_id) in scoped
            if provider == "telegram":
                return True
            if provider == "bitrix":
                return str(x.external_id or "").strip() in portal_bitrix_external_ids
            return False

        bitrix = [
            {"id": x.id, "external_id": x.external_id, "display_value": x.display_value, "integration_id": x.integration_id}
            for x in idents
            if (x.provider or "").lower() == "bitrix" and _identity_visible(x)
        ]
        telegram = [
            {"id": x.id, "external_id": x.external_id, "display_value": x.display_value, "integration_id": x.integration_id}
            for x in idents
            if (x.provider or "").lower() == "telegram" and _identity_visible(x)
        ]
        amo = [
            {"id": x.id, "external_id": x.external_id, "display_value": x.display_value, "integration_id": x.integration_id}
            for x in idents
            if (x.provider or "").lower() == "amo" and _identity_visible(x)
        ]
        items.append(
            {
                "membership_id": m.id,
                "user_id": uid,
                "display_name": (u.display_name if u else None),
                "role": m.role,
                "status": m.status,
                "permissions": {
                    "kb_access": normalize_kb_access_level(p.kb_access if p else "none"),
                    "can_invite_users": bool(p.can_invite_users) if p else False,
                    "can_manage_settings": bool(p.can_manage_settings) if p else False,
                    "can_view_finance": bool(p.can_view_finance) if p else False,
                },
                "web": (
                    {
                        "login": c.login,
                        "email": c.email,
                        "email_verified_at": c.email_verified_at.isoformat() if c.email_verified_at else None,
                    }
                    if c
                    else None
                ),
                "bitrix": bitrix,
                "telegram": telegram,
                "amo": amo,
            }
        )
    return items


def _build_account_user_groups_items(db: Session, account_id: int) -> list[dict]:
    groups = db.execute(
        select(AccountUserGroup)
        .where(AccountUserGroup.account_id == int(account_id))
        .order_by(AccountUserGroup.name.asc(), AccountUserGroup.id.asc())
    ).scalars().all()
    if not groups:
        return []
    group_ids = [int(g.id) for g in groups]
    member_rows = db.execute(
        select(AccountUserGroupMember.group_id, AccountUserGroupMember.membership_id)
        .where(AccountUserGroupMember.group_id.in_(group_ids))
    ).all()
    membership_ids = sorted({int(row[1]) for row in member_rows if row[1] is not None})
    memberships = []
    if membership_ids:
        memberships = db.execute(
            select(AccountMembership).where(
                AccountMembership.account_id == int(account_id),
                AccountMembership.id.in_(membership_ids),
            )
        ).scalars().all()
    membership_map = {int(m.id): m for m in memberships}
    members_by_group: dict[int, list[dict[str, object]]] = {int(g.id): [] for g in groups}
    for group_id, membership_id in member_rows:
        membership = membership_map.get(int(membership_id))
        if not membership:
            continue
        members_by_group.setdefault(int(group_id), []).append(
            {
                "membership_id": int(membership.id),
                "user_id": int(membership.user_id),
                "role": str(membership.role or "member"),
                "status": str(membership.status or "active"),
            }
        )
    items: list[dict] = []
    for group in groups:
        members = sorted(members_by_group.get(int(group.id), []), key=lambda item: int(item["membership_id"]))
        items.append(
            {
                "id": int(group.id),
                "name": str(group.name or ""),
                "kind": str(group.kind or "staff"),
                "membership_ids": [int(item["membership_id"]) for item in members],
                "members": members,
            }
        )
    return items


def _validate_group_memberships_for_kind(
    db: Session,
    *,
    account_id: int,
    membership_ids: list[int],
    kind: str,
) -> None:
    if not membership_ids:
        return
    rows = db.execute(
        select(AccountMembership.id, AccountMembership.role).where(
            AccountMembership.account_id == int(account_id),
            AccountMembership.id.in_(membership_ids),
            AccountMembership.status.in_(["active", "invited"]),
        )
    ).all()
    if len({int(row[0]) for row in rows}) != len(membership_ids):
        raise HTTPException(status_code=400, detail="invalid_membership_ids")
    if kind == "client":
        invalid = [int(row[0]) for row in rows if str(row[1] or "").lower() != "client"]
    else:
        invalid = [int(row[0]) for row in rows if str(row[1] or "").lower() == "client"]
    if invalid:
        raise HTTPException(status_code=400, detail="group_members_kind_mismatch")


def _ensure_legacy_web_user(
    db: Session,
    *,
    account_id: int,
    email: str,
    password_hash: str,
    email_verified_at: datetime | None = None,
) -> None:
    email_l = (email or "").strip().lower()
    if not email_l:
        return
    portal_id = _resolve_account_portal_id(db, int(account_id))
    if not portal_id:
        return
    now = datetime.utcnow()
    wu = db.execute(select(WebUser).where(WebUser.email == email_l)).scalar_one_or_none()
    if not wu:
        wu = WebUser(
            email=email_l,
            password_hash=password_hash,
            portal_id=portal_id,
            email_verified_at=email_verified_at or now,
            created_at=now,
            updated_at=now,
        )
        db.add(wu)
        return
    wu.password_hash = password_hash
    if not wu.portal_id:
        wu.portal_id = portal_id
    if (wu.email_verified_at is None) and (email_verified_at is not None):
        wu.email_verified_at = email_verified_at
    wu.updated_at = now
    db.add(wu)


@router.get("/auth/me")
def web_v2_me(
    session: WebSession = Depends(_get_current_web_session),
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    account_id = None
    app_session = db.execute(select(AppSession).where(AppSession.token == session.token)).scalar_one_or_none()
    if app_session and app_session.active_account_id:
        account_id = int(app_session.active_account_id)
    elif user.portal_id:
        account_id = get_account_id_by_portal_id(db, int(user.portal_id or 0))
    membership = get_membership_ctx(db, int(account_id), user) if account_id else None
    acc = db.get(Account, int(account_id)) if account_id else None
    return {
        "user": {"id": user.id, "email": user.email},
        "account": {"id": account_id, "account_no": (acc.account_no if acc else None)},
        "membership": (
            {
                "role": membership.role,
                "kb_access": normalize_kb_access_level(membership.kb_access),
                "can_invite_users": membership.can_invite_users,
                "can_manage_settings": membership.can_manage_settings,
                "can_view_finance": membership.can_view_finance,
            }
            if membership
            else None
        ),
    }


@router.get("/accounts/{account_id}/permissions/schema")
def web_v2_permissions_schema(
    account_id: int,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    require_membership_ctx(db, account_id, user)
    return {
        "role": ["owner", "admin", "member", "client"],
        "kb_access": ["none", "read", "upload", "edit", "manage"],
        "flags": ["can_invite_users", "can_manage_settings", "can_view_finance"],
    }


@router.get("/billing/plans")
def web_v2_billing_plans(
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    return {
        "items": [item for item in list_billing_plans(db) if item.get("is_active")],
    }


@router.get("/accounts/{account_id}/billing")
def web_v2_account_billing(
    account_id: int,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    membership = require_membership_ctx(db, account_id, user)
    account = db.get(Account, account_id)
    return {
        "account": {
            "id": account_id,
            "name": account.name if account else None,
            "account_no": account.account_no if account else None,
            "slug": account.slug if account else None,
        },
        "membership": {
            "role": membership.role,
            "can_view_finance": membership.can_view_finance,
        },
        "subscription": get_account_subscription_payload(db, account_id).get("subscription"),
        "effective_policy": get_account_effective_policy(db, account_id),
        "usage": get_account_usage_summary(db, account_id),
    }


@router.get("/accounts/{account_id}/users")
def web_v2_list_users(
    account_id: int,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    require_membership_ctx(db, account_id, user)
    return {"items": _build_account_users_items(db, account_id)}


@router.get("/accounts/{account_id}/access-center")
def web_v2_access_center(
    account_id: int,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    require_membership_ctx(db, account_id, user)
    items = _build_account_users_items(db, account_id)
    user_groups = _build_account_user_groups_items(db, account_id)
    groups_by_membership: dict[int, list[dict[str, object]]] = {}
    for group in user_groups:
        ref = {"id": int(group["id"]), "name": str(group["name"]), "kind": str(group.get("kind") or "staff")}
        for membership_id in group.get("membership_ids", []):
            groups_by_membership.setdefault(int(membership_id), []).append(ref)
    portal_id = _resolve_account_portal_id(db, account_id)
    access_rows = []
    if portal_id:
        access_rows = db.execute(
            select(PortalUsersAccess).where(PortalUsersAccess.portal_id == int(portal_id))
        ).scalars().all()
    bitrix_access = [r for r in access_rows if (r.kind or "bitrix") == "bitrix"]
    legacy_web = [r for r in access_rows if (r.kind or "") == "web"]
    bitrix_by_uid = {str(r.user_id): r for r in bitrix_access}

    for item in items:
        bitrix_ids = [str(x.get("external_id") or "").strip() for x in (item.get("bitrix") or []) if str(x.get("external_id") or "").strip()]
        matched_rows = [bitrix_by_uid[x] for x in bitrix_ids if x in bitrix_by_uid]
        item["access_center"] = {
            "portal_id": portal_id,
            "bitrix_linked": bool(bitrix_ids),
            "bitrix_allowlist": bool(matched_rows),
            "bitrix_user_ids": bitrix_ids,
            "telegram_username": next((r.telegram_username for r in matched_rows if r.telegram_username), None),
        }
        item["groups"] = sorted(
            groups_by_membership.get(int(item["membership_id"]), []),
            key=lambda group: (str(group["name"]).lower(), int(group["id"])),
        )

    extras = [
        {
            "id": r.id,
            "user_id": r.user_id,
            "display_name": r.display_name,
            "telegram_username": r.telegram_username,
            "kind": r.kind,
        }
        for r in legacy_web
    ]
    return {
        "portal_id": portal_id,
        "items": items,
        "groups": user_groups,
        "legacy_web_users": extras,
    }


@router.get("/accounts/{account_id}/user-groups")
def web_v2_list_user_groups(
    account_id: int,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    require_membership_ctx(db, account_id, user)
    return {"account_id": account_id, "items": _build_account_user_groups_items(db, account_id)}


@router.post("/accounts/{account_id}/user-groups")
def web_v2_create_user_group(
    account_id: int,
    body: AccountUserGroupBody,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    ctx = require_membership_ctx(db, account_id, user)
    require_settings_permission(ctx)
    name = str(body.name or "").strip()
    kind = _normalize_group_kind(body.kind)
    if not name:
        raise HTTPException(status_code=400, detail="invalid_group_name")
    existing = db.execute(
        select(AccountUserGroup.id).where(
            AccountUserGroup.account_id == int(account_id),
            AccountUserGroup.name == name,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=400, detail="group_name_taken")
    membership_ids = sorted({int(x) for x in body.membership_ids if int(x) > 0})
    _validate_group_memberships_for_kind(
        db,
        account_id=int(account_id),
        membership_ids=membership_ids,
        kind=kind,
    )
    group = AccountUserGroup(account_id=int(account_id), name=name, kind=kind)
    db.add(group)
    db.flush()
    for membership_id in membership_ids:
        db.add(AccountUserGroupMember(group_id=int(group.id), membership_id=int(membership_id)))
    db.commit()
    items = _build_account_user_groups_items(db, account_id)
    payload = next((item for item in items if int(item["id"]) == int(group.id)), None)
    return {"status": "ok", "group": payload}


@router.patch("/accounts/{account_id}/user-groups/{group_id}")
def web_v2_update_user_group(
    account_id: int,
    group_id: int,
    body: AccountUserGroupBody,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    ctx = require_membership_ctx(db, account_id, user)
    require_settings_permission(ctx)
    group = db.execute(
        select(AccountUserGroup).where(
            AccountUserGroup.id == int(group_id),
            AccountUserGroup.account_id == int(account_id),
        )
    ).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="group_not_found")
    name = str(body.name or "").strip()
    kind = _normalize_group_kind(body.kind)
    if not name:
        raise HTTPException(status_code=400, detail="invalid_group_name")
    existing = db.execute(
        select(AccountUserGroup.id).where(
            AccountUserGroup.account_id == int(account_id),
            AccountUserGroup.name == name,
            AccountUserGroup.id != int(group.id),
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=400, detail="group_name_taken")
    membership_ids = sorted({int(x) for x in body.membership_ids if int(x) > 0})
    _validate_group_memberships_for_kind(
        db,
        account_id=int(account_id),
        membership_ids=membership_ids,
        kind=kind,
    )
    group.name = name
    group.kind = kind
    group.updated_at = datetime.utcnow()
    db.add(group)
    db.execute(delete(AccountUserGroupMember).where(AccountUserGroupMember.group_id == int(group.id)))
    for membership_id in membership_ids:
        db.add(AccountUserGroupMember(group_id=int(group.id), membership_id=int(membership_id)))
    db.commit()
    items = _build_account_user_groups_items(db, account_id)
    payload = next((item for item in items if int(item["id"]) == int(group.id)), None)
    return {"status": "ok", "group": payload}


@router.delete("/accounts/{account_id}/user-groups/{group_id}")
def web_v2_delete_user_group(
    account_id: int,
    group_id: int,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    ctx = require_membership_ctx(db, account_id, user)
    require_settings_permission(ctx)
    group = db.execute(
        select(AccountUserGroup).where(
            AccountUserGroup.id == int(group_id),
            AccountUserGroup.account_id == int(account_id),
        )
    ).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="group_not_found")
    db.delete(group)
    db.commit()
    return {"status": "ok", "group_id": int(group_id)}


@router.get("/accounts/{account_id}/integrations/bitrix")
def web_v2_list_bitrix_integrations(
    account_id: int,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    require_membership_ctx(db, account_id, user)
    return {"account_id": account_id, "items": _list_bitrix_integrations(db, account_id)}


@router.post("/accounts/{account_id}/integrations/bitrix/{integration_id}/make-primary")
def web_v2_make_bitrix_integration_primary(
    account_id: int,
    integration_id: int,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    ctx = require_membership_ctx(db, account_id, user)
    require_settings_permission(ctx)
    target = db.execute(
        select(AccountIntegration).where(
            AccountIntegration.id == int(integration_id),
            AccountIntegration.account_id == int(account_id),
            AccountIntegration.provider == "bitrix",
            AccountIntegration.status == "active",
        )
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="integration_not_found")
    rows = db.execute(
        select(AccountIntegration).where(
            AccountIntegration.account_id == int(account_id),
            AccountIntegration.provider == "bitrix",
        )
    ).scalars().all()
    for row in rows:
        meta = dict(row.credentials_json or {})
        meta["is_primary"] = int(row.id) == int(target.id)
        row.credentials_json = meta
        row.updated_at = datetime.utcnow()
        db.add(row)
    _sync_account_bridge_portal(db, int(account_id), int(target.portal_id) if target.portal_id else None)
    db.commit()
    return {
        "status": "ok",
        "account_id": account_id,
        "primary_integration_id": int(target.id),
        "items": _list_bitrix_integrations(db, account_id),
    }


@router.delete("/accounts/{account_id}/integrations/bitrix/{integration_id}")
def web_v2_disconnect_bitrix_integration(
    account_id: int,
    integration_id: int,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    ctx = require_membership_ctx(db, account_id, user)
    require_settings_permission(ctx)
    target = db.execute(
        select(AccountIntegration).where(
            AccountIntegration.id == int(integration_id),
            AccountIntegration.account_id == int(account_id),
            AccountIntegration.provider == "bitrix",
            AccountIntegration.status == "active",
        )
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="integration_not_found")

    was_primary = bool(dict(target.credentials_json or {}).get("is_primary"))
    if target.portal_id:
        portal = db.get(Portal, int(target.portal_id))
        if portal and int(portal.account_id or 0) == int(account_id):
            portal.account_id = None
            db.add(portal)
    meta = dict(target.credentials_json or {})
    meta["is_primary"] = False
    target.credentials_json = meta
    target.status = "deleted"
    target.updated_at = datetime.utcnow()
    db.add(target)

    new_primary_portal_id: int | None = None
    if was_primary:
        replacement = db.execute(
            select(AccountIntegration).where(
                AccountIntegration.account_id == int(account_id),
                AccountIntegration.provider == "bitrix",
                AccountIntegration.status == "active",
                AccountIntegration.id != int(target.id),
            ).order_by(AccountIntegration.id.asc())
        ).scalars().first()
        if replacement:
            replacement_meta = dict(replacement.credentials_json or {})
            replacement_meta["is_primary"] = True
            replacement.credentials_json = replacement_meta
            replacement.updated_at = datetime.utcnow()
            db.add(replacement)
            new_primary_portal_id = int(replacement.portal_id) if replacement.portal_id else None
    if was_primary:
        _sync_account_bridge_portal(db, int(account_id), new_primary_portal_id)
    db.commit()
    return {
        "status": "ok",
        "account_id": account_id,
        "disconnected_integration_id": int(integration_id),
        "items": _list_bitrix_integrations(db, account_id),
    }


@router.post("/accounts/{account_id}/users/manual")
def web_v2_create_manual_user(
    account_id: int,
    body: ManualUserBody,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    ctx = require_membership_ctx(db, account_id, user)
    require_invite_permission(ctx)

    login = (body.login or "").strip().lower()
    if not login:
        raise HTTPException(status_code=400, detail="login_required")
    if len(body.password or "") < 6:
        raise HTTPException(status_code=400, detail="password_too_short")
    role = _normalize_role(body.role, allow_owner=False)
    email = (str(body.email).strip().lower() if body.email else None)

    login_exists = db.execute(
        select(AppUserWebCredential.user_id).where(AppUserWebCredential.login == login)
    ).first()
    if login_exists:
        raise HTTPException(status_code=409, detail="login_exists")
    if email:
        email_exists = db.execute(
            select(AppUserWebCredential.user_id).where(AppUserWebCredential.email == email)
        ).first()
        if email_exists:
            raise HTTPException(status_code=409, detail="email_exists")
    if is_account_user_limit_reached(db, account_id, extra_users=1):
        raise HTTPException(status_code=403, detail="max_users_limit_reached")

    app_user = AppUser(
        display_name=(body.display_name or "").strip() or (email or login),
        status="active",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(app_user)
    db.flush()

    cred = AppUserWebCredential(
        user_id=int(app_user.id),
        login=login,
        email=email,
        password_hash=_hash_password(body.password),
        email_verified_at=None,
        must_change_password=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(cred)

    membership = AccountMembership(
        account_id=account_id,
        user_id=int(app_user.id),
        role=role,
        status="active",
        invited_by_user_id=ctx.app_user_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(membership)
    db.flush()
    perm_values = _build_permissions(role, body)
    _upsert_permissions(db, int(membership.id), perm_values)
    db.commit()
    return {
        "status": "ok",
        "user_id": int(app_user.id),
        "membership_id": int(membership.id),
        "login": login,
        "email": email,
    }


@router.patch("/accounts/{account_id}/users/{user_id}")
def web_v2_update_user(
    account_id: int,
    user_id: int,
    body: UpdateUserBody,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    ctx = require_membership_ctx(db, account_id, user)
    require_settings_permission(ctx)

    app_user = db.get(AppUser, user_id)
    if not app_user:
        raise HTTPException(status_code=404, detail="user_not_found")
    membership = _membership_by_account_user(db, account_id, user_id)
    if not membership:
        raise HTTPException(status_code=404, detail="membership_not_found")

    if body.display_name is not None:
        app_user.display_name = body.display_name.strip() or None
        app_user.updated_at = datetime.utcnow()

    if membership.role == "owner" and (
        body.role is not None
        or body.status is not None
        or body.kb_access is not None
        or body.can_invite_users is not None
        or body.can_manage_settings is not None
        or body.can_view_finance is not None
    ):
        raise HTTPException(status_code=400, detail="owner_immutable")

    role = membership.role
    if body.role is not None:
        role = _normalize_role(body.role, allow_owner=False)
        membership.role = role
    if body.status is not None:
        membership.status = _normalize_membership_status(body.status)
    membership.updated_at = datetime.utcnow()
    perm_values = _build_permissions(role, body)
    _upsert_permissions(db, int(membership.id), perm_values)

    db.add(app_user)
    db.add(membership)
    db.commit()
    return {"status": "ok"}


@router.patch("/accounts/{account_id}/memberships/{membership_id}/permissions")
def web_v2_update_membership_permissions(
    account_id: int,
    membership_id: int,
    body: UpdateMembershipPermissionsBody,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    ctx = require_membership_ctx(db, account_id, user)
    require_settings_permission(ctx)

    membership = db.execute(
        select(AccountMembership).where(
            AccountMembership.id == membership_id,
            AccountMembership.account_id == account_id,
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="membership_not_found")
    if membership.role == "owner":
        raise HTTPException(status_code=400, detail="owner_immutable")

    role = membership.role
    if body.role is not None:
        role = _normalize_role(body.role, allow_owner=False)
        membership.role = role
    if body.status is not None:
        membership.status = _normalize_membership_status(body.status)
    membership.updated_at = datetime.utcnow()
    perm_values = _build_permissions(role, body)
    _upsert_permissions(db, int(membership.id), perm_values)
    db.add(membership)
    db.commit()
    return {"status": "ok"}


@router.patch("/accounts/{account_id}/memberships/{membership_id}/telegram")
def web_v2_update_membership_telegram_identity(
    account_id: int,
    membership_id: int,
    body: UpdateTelegramIdentityBody,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    ctx = require_membership_ctx(db, account_id, user)
    require_invite_permission(ctx)

    membership = db.execute(
        select(AccountMembership).where(
            AccountMembership.id == membership_id,
            AccountMembership.account_id == account_id,
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="membership_not_found")

    uname = normalize_telegram_username(body.telegram_username)
    existing = db.execute(
        select(AppUserIdentity).where(
            AppUserIdentity.user_id == membership.user_id,
            AppUserIdentity.provider == "telegram",
            AppUserIdentity.integration_id.is_(None),
        )
    ).scalar_one_or_none()

    if uname:
        duplicate = db.execute(
            select(AppUserIdentity).where(
                AppUserIdentity.provider == "telegram",
                AppUserIdentity.integration_id.is_(None),
                AppUserIdentity.external_id == uname,
                AppUserIdentity.user_id != membership.user_id,
            )
        ).scalar_one_or_none()
        if duplicate:
            raise HTTPException(status_code=400, detail="duplicate_telegram_username")
        if not existing:
            existing = AppUserIdentity(
                user_id=membership.user_id,
                provider="telegram",
                integration_id=None,
                external_id=uname,
                display_value=f"@{uname}",
                created_at=datetime.utcnow(),
            )
        else:
            existing.external_id = uname
            existing.display_value = f"@{uname}"
        db.add(existing)
    elif existing:
        db.delete(existing)

    db.commit()
    return {"status": "ok", "telegram_username": uname}


@router.delete("/accounts/{account_id}/users/{user_id}")
def web_v2_delete_user(
    account_id: int,
    user_id: int,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    ctx = require_membership_ctx(db, account_id, user)
    require_settings_permission(ctx)

    membership = _membership_by_account_user(db, account_id, user_id)
    if not membership:
        return {"status": "ok"}
    if membership.role == "owner":
        raise HTTPException(status_code=400, detail="owner_immutable")
    membership.status = "deleted"
    membership.updated_at = datetime.utcnow()
    db.add(membership)
    db.commit()
    return {"status": "ok"}


@router.get("/accounts/{account_id}/invites")
def web_v2_list_invites(
    account_id: int,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    require_membership_ctx(db, account_id, user)
    rows = db.execute(
        select(AccountInvite)
        .where(AccountInvite.account_id == account_id)
        .order_by(AccountInvite.id.desc())
    ).scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "email": r.email,
                "login": r.login,
                "role": r.role,
                "status": r.status,
                "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "accepted_at": r.accepted_at.isoformat() if r.accepted_at else None,
                "accept_url": (build_invite_accept_url(r.token) if (r.status or "").lower() == "pending" else None),
            }
            for r in rows
        ]
    }


@router.post("/accounts/{account_id}/invites/email")
def web_v2_invite_by_email(
    account_id: int,
    body: InviteEmailBody,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    ctx = require_membership_ctx(db, account_id, user)
    require_invite_permission(ctx)

    role = _normalize_role(body.role, allow_owner=False)
    expires_days = max(1, min(int(body.expires_days or 7), 30))
    invite = AccountInvite(
        account_id=account_id,
        email=body.email.strip().lower(),
        login=None,
        role=role,
        permissions_json={
            "kb_access": body.kb_access,
            "can_invite_users": body.can_invite_users,
            "can_manage_settings": body.can_manage_settings,
            "can_view_finance": body.can_view_finance,
        },
        token=secrets.token_urlsafe(32),
        status="pending",
        invited_by_user_id=ctx.app_user_id,
        accepted_user_id=None,
        expires_at=datetime.utcnow() + timedelta(days=expires_days),
        created_at=datetime.utcnow(),
        accepted_at=None,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    acc = db.get(Account, account_id)
    send_account_invite_email(
        db,
        to_email=str(invite.email or "").strip().lower(),
        token=invite.token,
        account_name=(acc.name if acc else None),
    )
    return {
        "status": "ok",
        "invite_id": invite.id,
        "email": invite.email,
        "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
        "accept_url": build_invite_accept_url(invite.token),
    }


@router.post("/invites/{token}/accept")
def web_v2_accept_invite(
    token: str,
    body: AcceptInviteBody,
    db: Session = Depends(get_db),
):
    invite = db.execute(
        select(AccountInvite).where(AccountInvite.token == token)
    ).scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="invite_not_found")
    if (invite.status or "").lower() != "pending":
        raise HTTPException(status_code=400, detail="invite_not_pending")
    if invite.expires_at and invite.expires_at < datetime.utcnow():
        invite.status = "expired"
        db.add(invite)
        db.commit()
        raise HTTPException(status_code=400, detail="invite_expired")

    login = (body.login or "").strip().lower()
    if not login:
        raise HTTPException(status_code=400, detail="login_required")
    if len(body.password or "") < 6:
        raise HTTPException(status_code=400, detail="password_too_short")
    email = (str(body.email).strip().lower() if body.email else None) or (invite.email or None)

    cred = _credential_by_login_or_email(db, login=login, email=email)
    if cred:
        app_user_id = int(cred.user_id)
        if login != (cred.login or "").strip().lower():
            raise HTTPException(status_code=409, detail="login_mismatch")
    else:
        login_conflict = _credential_by_login_or_email(db, login=login)
        if login_conflict:
            raise HTTPException(status_code=409, detail="login_exists")
        if email:
            email_conflict = _credential_by_login_or_email(db, email=email)
            if email_conflict:
                app_user_id = int(email_conflict.user_id)
                cred = email_conflict
            else:
                app_user_id = None  # type: ignore[assignment]
        else:
            app_user_id = None  # type: ignore[assignment]

        if app_user_id is None:
            app_user = AppUser(
                display_name=(body.display_name or "").strip() or (email or login),
                status="active",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(app_user)
            db.flush()
            app_user_id = int(app_user.id)

        if not cred:
            cred = AppUserWebCredential(
                user_id=app_user_id,
                login=login,
                email=email,
                password_hash=_hash_password(body.password),
                email_verified_at=None,
                must_change_password=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(cred)
    if cred:
        cred.password_hash = _hash_password(body.password)
        if email and not cred.email:
            cred.email = email
        cred.updated_at = datetime.utcnow()
        db.add(cred)
        app_user_id = int(cred.user_id)

    membership = _membership_by_account_user(db, int(invite.account_id), int(app_user_id))
    role = _normalize_role(invite.role, allow_owner=False)
    if (membership is None or membership.status != "active") and is_account_user_limit_reached(db, int(invite.account_id), extra_users=1):
        raise HTTPException(status_code=403, detail="max_users_limit_reached")
    if not membership:
        membership = AccountMembership(
            account_id=int(invite.account_id),
            user_id=int(app_user_id),
            role=role,
            status="active",
            invited_by_user_id=invite.invited_by_user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(membership)
        db.flush()
    else:
        membership.role = role
        membership.status = "active"
        membership.updated_at = datetime.utcnow()
        db.add(membership)

    perm_values = _ROLE_DEFAULTS[role]
    if isinstance(invite.permissions_json, dict):
        perm_values = _build_permissions(role, type("InvitePerm", (), invite.permissions_json)())
    _upsert_permissions(db, int(membership.id), perm_values)

    invite.status = "accepted"
    invite.accepted_user_id = int(app_user_id)
    invite.accepted_at = datetime.utcnow()
    if email and cred:
        _ensure_legacy_web_user(
            db,
            account_id=int(invite.account_id),
            email=email,
            password_hash=cred.password_hash,
            email_verified_at=datetime.utcnow(),
        )
    db.add(invite)
    db.commit()
    return {
        "status": "ok",
        "account_id": int(invite.account_id),
        "user_id": int(app_user_id),
        "membership_id": int(membership.id),
    }


@router.post("/accounts/{account_id}/invites/{invite_id}/revoke")
def web_v2_revoke_invite(
    account_id: int,
    invite_id: int,
    user: WebUser = Depends(_get_current_web_user),
    db: Session = Depends(get_db),
):
    ctx = require_membership_ctx(db, account_id, user)
    require_invite_permission(ctx)
    invite = db.execute(
        select(AccountInvite).where(
            AccountInvite.id == invite_id,
            AccountInvite.account_id == account_id,
        )
    ).scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="invite_not_found")
    if (invite.status or "").lower() == "accepted":
        raise HTTPException(status_code=400, detail="invite_already_accepted")
    invite.status = "revoked"
    db.add(invite)
    db.commit()
    return {"status": "ok"}
