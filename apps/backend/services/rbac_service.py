"""RBAC v2 helpers for account/membership/permissions."""
from __future__ import annotations

import json
from datetime import datetime
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.backend.models.account import (
    Account,
    AccountIntegration,
    AccountMembership,
    AccountPermission,
    AppUser,
    AppUserWebCredential,
)
from apps.backend.models.portal import Portal
from apps.backend.models.web_user import WebUser
from apps.backend.services.account_workspace import build_unique_account_slug


@dataclass
class MembershipCtx:
    account_id: int
    app_user_id: int
    role: str
    kb_access: str
    can_invite_users: bool
    can_manage_settings: bool
    can_view_finance: bool


def _next_account_no(db: Session) -> int:
    max_no = db.execute(select(func.max(Account.account_no))).scalar()
    return int(max_no or 100000) + 1


def _is_owner_candidate(db: Session, portal: Portal, web_user: WebUser) -> bool:
    if (portal.install_type or "").strip().lower() == "web":
        return True
    owner_email = None
    try:
        meta = json.loads(portal.metadata_json or "{}") if portal.metadata_json else {}
        owner_email = (meta.get("owner_email") or "").strip().lower() or None
    except Exception:
        owner_email = None
    if owner_email and owner_email == (web_user.email or "").strip().lower():
        return True
    # If only one web user exists on portal, treat as owner candidate.
    web_users_count = db.execute(
        select(func.count(WebUser.id)).where(WebUser.portal_id == portal.id)
    ).scalar()
    return int(web_users_count or 0) <= 1


def ensure_rbac_for_web_user(
    db: Session,
    web_user: WebUser,
    *,
    force_owner: bool = False,
    account_name: str | None = None,
) -> tuple[int | None, int | None]:
    """
    Ensure account/app_user/membership + permissions exist for web user.
    Returns (account_id, app_user_id).
    """
    if not web_user or not web_user.portal_id:
        return None, None

    portal = db.get(Portal, int(web_user.portal_id))
    if not portal:
        return None, None

    now = datetime.utcnow()
    account_id = int(portal.account_id) if portal.account_id else None
    if not account_id:
        acc = Account(
            account_no=_next_account_no(db),
            name=(account_name or portal.domain or "").strip() or None,
            slug=None,
            status="active",
            owner_user_id=None,
            created_at=now,
            updated_at=now,
        )
        db.add(acc)
        db.flush()
        acc.slug = build_unique_account_slug(
            db,
            acc.name or portal.domain or None,
            fallback=f"workspace-{int(acc.account_no or acc.id)}",
            exclude_account_id=int(acc.id),
        )
        db.add(acc)
        account_id = int(acc.id)
        portal.account_id = account_id
        db.add(portal)

    email = (web_user.email or "").strip().lower()
    cred = None
    if email:
        cred = db.execute(
            select(AppUserWebCredential).where(AppUserWebCredential.email == email)
        ).scalar_one_or_none()
    if not cred:
        login = email or f"webuser_{int(web_user.id)}"
        cred = db.execute(
            select(AppUserWebCredential).where(AppUserWebCredential.login == login)
        ).scalar_one_or_none()

    if cred:
        app_user_id = int(cred.user_id)
        if email and not cred.email:
            cred.email = email
        if email and cred.login != email:
            cred.login = email
        cred.updated_at = now
        db.add(cred)
    else:
        app_user = AppUser(
            display_name=email or f"web_user_{int(web_user.id)}",
            status="active",
            created_at=now,
            updated_at=now,
        )
        db.add(app_user)
        db.flush()
        app_user_id = int(app_user.id)
        db.add(
            AppUserWebCredential(
                user_id=app_user_id,
                login=email or f"webuser_{int(web_user.id)}",
                email=email or None,
                password_hash=web_user.password_hash or "",
                email_verified_at=web_user.email_verified_at,
                must_change_password=False,
                created_at=now,
                updated_at=now,
            )
        )

    owner_mode = force_owner or _is_owner_candidate(db, portal, web_user)
    role = "owner" if owner_mode else "member"
    membership = db.execute(
        select(AccountMembership).where(
            AccountMembership.account_id == account_id,
            AccountMembership.user_id == app_user_id,
        )
    ).scalar_one_or_none()
    if not membership:
        membership = AccountMembership(
            account_id=account_id,
            user_id=app_user_id,
            role=role,
            status="active",
            invited_by_user_id=None,
            created_at=now,
            updated_at=now,
        )
        db.add(membership)
        db.flush()
    else:
        membership.status = "active"
        if owner_mode:
            membership.role = "owner"
        membership.updated_at = now
        db.add(membership)

    perm = db.execute(
        select(AccountPermission).where(AccountPermission.membership_id == int(membership.id))
    ).scalar_one_or_none()
    if not perm:
        perm = AccountPermission(
            membership_id=int(membership.id),
            kb_access="write" if owner_mode else "read",
            can_invite_users=bool(owner_mode),
            can_manage_settings=bool(owner_mode),
            can_view_finance=bool(owner_mode),
            updated_at=now,
        )
        db.add(perm)
    else:
        if owner_mode:
            perm.kb_access = "write"
            perm.can_invite_users = True
            perm.can_manage_settings = True
            perm.can_view_finance = True
        elif perm.kb_access not in ("read", "write"):
            perm.kb_access = "read"
        perm.updated_at = now
        db.add(perm)

    acc = db.get(Account, account_id)
    if acc:
        if owner_mode and int(acc.owner_user_id or 0) != app_user_id:
            acc.owner_user_id = app_user_id
        if not (acc.slug or "").strip():
            acc.slug = build_unique_account_slug(
                db,
                acc.name or portal.domain or None,
                fallback=f"workspace-{int(acc.account_no or acc.id)}",
                exclude_account_id=int(acc.id),
            )
        acc.updated_at = now
        db.add(acc)

    # Keep bitrix integration row for account/portal to avoid split in admin.
    domain = (portal.domain or "").strip().lower()
    install_type = (portal.install_type or "").strip().lower()
    is_bitrix = ("bitrix24." in domain) or install_type in ("local", "market")
    if is_bitrix and domain:
        integ = db.execute(
            select(AccountIntegration).where(
                AccountIntegration.provider == "bitrix",
                AccountIntegration.external_key == domain,
            )
        ).scalar_one_or_none()
        if not integ:
            db.add(
                AccountIntegration(
                    account_id=account_id,
                    provider="bitrix",
                    status="active",
                    external_key=domain,
                    portal_id=int(portal.id),
                    credentials_json=None,
                    created_at=now,
                    updated_at=now,
                )
            )
        elif int(integ.account_id) != account_id or int(integ.portal_id or 0) != int(portal.id):
            integ.account_id = account_id
            integ.portal_id = int(portal.id)
            integ.updated_at = now
            db.add(integ)

    return account_id, app_user_id


def get_account_id_by_portal_id(db: Session, portal_id: int) -> int | None:
    row = db.execute(select(Portal.account_id).where(Portal.id == portal_id)).first()
    if not row:
        return None
    account_id = row[0]
    return int(account_id) if account_id is not None else None


def ensure_account_member(
    db: Session,
    *,
    account_id: int,
    user_id: int,
    role: str = "member",
    status: str = "active",
    kb_access: str = "none",
    can_invite_users: bool = False,
    can_manage_settings: bool = False,
    can_view_finance: bool = False,
) -> tuple[AccountMembership, bool]:
    now = datetime.utcnow()
    membership = db.execute(
        select(AccountMembership).where(
            AccountMembership.account_id == int(account_id),
            AccountMembership.user_id == int(user_id),
        )
    ).scalar_one_or_none()
    created = False
    if not membership:
        membership = AccountMembership(
            account_id=int(account_id),
            user_id=int(user_id),
            role=(role or "member").strip().lower() or "member",
            status=(status or "active").strip().lower() or "active",
            invited_by_user_id=None,
            created_at=now,
            updated_at=now,
        )
        db.add(membership)
        db.flush()
        created = True

    perm = db.execute(
        select(AccountPermission).where(AccountPermission.membership_id == int(membership.id))
    ).scalar_one_or_none()
    if not perm:
        db.add(
            AccountPermission(
                membership_id=int(membership.id),
                kb_access=(kb_access or "none").strip().lower() or "none",
                can_invite_users=bool(can_invite_users),
                can_manage_settings=bool(can_manage_settings),
                can_view_finance=bool(can_view_finance),
                updated_at=now,
            )
        )
    return membership, created


def get_app_user_id_by_web_user(db: Session, web_user: WebUser) -> int | None:
    email = (web_user.email or "").strip().lower()
    if not email:
        return None
    row = db.execute(
        select(AppUserWebCredential.user_id).where(AppUserWebCredential.email == email)
    ).first()
    if not row:
        return None
    return int(row[0])


def get_membership_ctx(db: Session, account_id: int, web_user: WebUser) -> MembershipCtx | None:
    app_user_id = get_app_user_id_by_web_user(db, web_user)
    if not app_user_id:
        return None
    membership = db.execute(
        select(AccountMembership).where(
            AccountMembership.account_id == account_id,
            AccountMembership.user_id == app_user_id,
            AccountMembership.status.in_(["active", "invited"]),
        )
    ).scalar_one_or_none()
    if not membership:
        return None
    perm = db.execute(
        select(AccountPermission).where(AccountPermission.membership_id == membership.id)
    ).scalar_one_or_none()
    return MembershipCtx(
        account_id=int(account_id),
        app_user_id=int(app_user_id),
        role=str(membership.role or "member"),
        kb_access=str((perm.kb_access if perm else None) or "none"),
        can_invite_users=bool(perm.can_invite_users) if perm else False,
        can_manage_settings=bool(perm.can_manage_settings) if perm else False,
        can_view_finance=bool(perm.can_view_finance) if perm else False,
    )


def require_membership_ctx(db: Session, account_id: int, web_user: WebUser) -> MembershipCtx:
    ctx = get_membership_ctx(db, account_id, web_user)
    if not ctx:
        raise HTTPException(status_code=403, detail="forbidden")
    return ctx


def is_owner_or_admin(ctx: MembershipCtx) -> bool:
    return ctx.role in ("owner", "admin")


def require_invite_permission(ctx: MembershipCtx) -> None:
    if is_owner_or_admin(ctx) or ctx.can_invite_users:
        return
    raise HTTPException(status_code=403, detail="forbidden")


def require_settings_permission(ctx: MembershipCtx) -> None:
    if is_owner_or_admin(ctx) or ctx.can_manage_settings:
        return
    raise HTTPException(status_code=403, detail="forbidden")


def require_finance_permission(ctx: MembershipCtx) -> None:
    if is_owner_or_admin(ctx) or ctx.can_view_finance:
        return
    raise HTTPException(status_code=403, detail="forbidden")


def require_kb_read_permission(ctx: MembershipCtx) -> None:
    if ctx.kb_access in ("read", "write") or is_owner_or_admin(ctx):
        return
    raise HTTPException(status_code=403, detail="forbidden")


def require_kb_write_permission(ctx: MembershipCtx) -> None:
    if ctx.kb_access == "write" or is_owner_or_admin(ctx):
        return
    raise HTTPException(status_code=403, detail="forbidden")
