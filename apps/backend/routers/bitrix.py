from __future__ import annotations

"""Bitrix OAuth, install, handler, events."""
import json
import logging
import os
import re
import uuid
import time
import hmac
import math
import secrets
import importlib.util
from urllib.parse import quote
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Request, Depends, UploadFile, File, HTTPException, Form
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse, PlainTextResponse, FileResponse

from pydantic import BaseModel, EmailStr

from sqlalchemy.orm import Session
import sqlalchemy as sa
from sqlalchemy import select, delete, func

from apps.backend.deps import get_db
from apps.backend.config import get_settings
from apps.backend.models.portal import Portal, PortalUsersAccess
from apps.backend.models.dialog import Dialog, Message
from apps.backend.models.bitrix_log import BitrixHttpLog
from apps.backend.models.kb import (
    KBFile,
    KBJob,
    KBSource,
    KBChunk,
    KBEmbedding,
    KBCollection,
    KBCollectionFile,
    KBSmartFolder,
    KBFolder,
    KBFolderAccess,
    KBFileAccess,
)
from apps.backend.auth import (
    create_portal_token_with_user,
    require_portal_access,
    decode_token,
    get_password_hash,
    verify_password,
)
from apps.backend.clients.bitrix import exchange_code, user_current, user_get
from apps.backend.services.bitrix_events import process_imbot_message
from apps.backend.services.portal_tokens import save_tokens, get_valid_access_token, BitrixAuthError, refresh_portal_tokens
from apps.backend.services.token_crypto import encrypt_token
from apps.backend.services.kb_storage import ensure_portal_dir, save_upload
from apps.backend.services.billing import (
    get_account_bitrix_portal_count,
    get_account_effective_policy,
    get_portal_effective_policy,
    is_account_bitrix_portal_limit_reached,
    would_exceed_account_media_minutes,
)
from apps.backend.services.kb_settings import (
    get_portal_kb_settings,
    set_portal_kb_settings,
    is_media_transcription_enabled,
    is_speaker_diarization_enabled,
)
from apps.backend.services.kb_sources import create_url_source
from apps.backend.services.kb_acl import (
    KB_ACCESS_LEVELS,
    default_kb_access_for_role,
    kb_acl_principals_for_membership,
    normalize_kb_principal,
    resolve_kb_acl_access,
)
from apps.backend.services.kb_rag import answer_from_kb
from apps.backend.services.gigachat_client import list_models, DEFAULT_API_BASE
from apps.backend.services.kb_settings import get_valid_gigachat_access_token
from apps.backend.services.portal_tokens import get_access_token
from apps.backend.services.bot_provisioning import ensure_bot_registered
from apps.backend.services.finalize_install import step_provision_chats, _now_trace_id
from apps.backend.services.finalize_install import finalize_install, step_provision_chats
from apps.backend.services.bot_provisioning import ensure_bot_registered
from apps.backend.clients.bitrix import imbot_bot_list, BOT_CODE_DEFAULT
from apps.backend.utils.bitrix_request import parse_bitrix_body
from apps.backend.services.telegram_settings import (
    normalize_telegram_username,
    get_portal_telegram_settings,
    set_portal_telegram_settings,
    get_portal_telegram_secret,
    get_portal_telegram_token_plain,
)
from apps.backend.models.web_user import WebUser, WebSession
from apps.backend.models.account import (
    Account,
    AccountIntegration,
    AccountMembership,
    AccountPermission,
    AccountUserGroup,
    AccountUserGroupMember,
    AppUserIdentity,
    AppUserWebCredential,
    AppSession,
)
from apps.backend.services.activity import log_activity
from apps.backend.clients.telegram import telegram_get_me, telegram_set_webhook
from apps.backend.services.web_email import create_email_token, send_registration_email
from apps.backend.services.rbac_service import ensure_account_member, ensure_rbac_for_web_user
from apps.backend.services.account_workspace import build_unique_account_slug
from apps.backend.services.transcript_utils import merge_transcript_items
from apps.backend.utils.api_errors import error_envelope
from apps.backend.utils.api_schema import is_schema_v2

router = APIRouter()

_install_html: str | None = None
_handler_html: str | None = None
_app_html: str | None = None


def _resolve_linked_web_user(db: Session, portal: Portal | None) -> WebUser | None:
    if not portal:
        return None

    owner_email = None
    if portal.metadata_json:
        try:
            meta = json.loads(portal.metadata_json) if isinstance(portal.metadata_json, str) else portal.metadata_json
            owner_email = (meta.get("owner_email") or "").strip().lower() or None
        except Exception:
            owner_email = None

    if owner_email:
        user = db.execute(select(WebUser).where(WebUser.email == owner_email)).scalars().first()
        if user and int(user.portal_id or 0) == int(portal.id):
            return user

    if portal.account_id:
        owner_row = db.execute(
            select(AppUserWebCredential.email)
            .join(Account, Account.owner_user_id == AppUserWebCredential.user_id)
            .where(Account.id == int(portal.account_id))
            .limit(1)
        ).first()
        owner_account_email = (str(owner_row[0]).strip().lower() if owner_row and owner_row[0] else None)
        if owner_account_email:
            user = db.execute(select(WebUser).where(WebUser.email == owner_account_email)).scalars().first()
            if user:
                return user

    return (
        db.execute(
            select(WebUser)
            .where(WebUser.portal_id == int(portal.id))
            .order_by(
                WebUser.email_verified_at.isnot(None).desc(),
                WebUser.created_at.asc(),
                WebUser.id.asc(),
            )
        )
        .scalars()
        .first()
    )


def _authenticate_web_user_for_bitrix(db: Session, email: str, password: str) -> WebUser:
    normalized_email = (email or "").strip().lower()
    user = db.execute(select(WebUser).where(WebUser.email == normalized_email)).scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid_credentials")
    if not user.email_verified_at:
        raise HTTPException(status_code=403, detail="email_not_verified")
    return user


def _get_app_user_id_for_web_user(db: Session, web_user: WebUser) -> int | None:
    email = (web_user.email or "").strip().lower()
    if not email:
        return None
    cred = db.execute(select(AppUserWebCredential).where(AppUserWebCredential.email == email)).scalar_one_or_none()
    if not cred:
        return None
    return int(cred.user_id)


def _portal_account_membership_ctx(db: Session, portal_id: int, web_user: WebUser) -> dict[str, Any] | None:
    portal = db.get(Portal, int(portal_id))
    if not portal or not portal.account_id:
        return None
    app_user_id = _get_app_user_id_for_web_user(db, web_user)
    if not app_user_id:
        return None
    row = db.execute(
        select(AccountMembership, AccountPermission)
        .join(AccountPermission, AccountPermission.membership_id == AccountMembership.id, isouter=True)
        .where(AccountMembership.account_id == int(portal.account_id))
        .where(AccountMembership.user_id == int(app_user_id))
        .where(AccountMembership.status == "active")
        .limit(1)
    ).first()
    if not row:
        return None
    membership, perm = row
    return {
        "account_id": int(portal.account_id),
        "membership_id": int(membership.id),
        "role": str(membership.role or "member"),
        "can_manage_integrations": str(membership.role or "member") in {"owner", "admin"} or bool(
            perm.can_manage_settings if perm else False
        ),
    }


def _portal_acl_subject_ctx(
    db: Session,
    *,
    portal_id: int,
    request: Request,
    audience: str,
) -> dict[str, Any]:
    portal = db.get(Portal, int(portal_id))
    uid = _portal_user_id_from_token(request)
    role = "client" if str(audience or "").strip().lower() == "client" else "member"
    membership_id: int | None = None
    if uid and portal and portal.admin_user_id and int(portal.admin_user_id) == int(uid):
        role = "admin"
    if not portal or not portal.account_id or not uid:
        return {"membership_id": membership_id, "group_ids": [], "role": role, "audience": audience, "portal_user_id": uid}
    integ = db.execute(
        select(AccountIntegration)
        .where(
            AccountIntegration.provider == "bitrix",
            AccountIntegration.portal_id == int(portal_id),
        )
        .order_by(AccountIntegration.id.asc())
        .limit(1)
    ).scalar_one_or_none()
    if not integ:
        return {"membership_id": membership_id, "group_ids": [], "role": role, "audience": audience, "portal_user_id": uid}
    ident = db.execute(
        select(AppUserIdentity)
        .where(
            AppUserIdentity.provider == "bitrix",
            AppUserIdentity.integration_id == int(integ.id),
            AppUserIdentity.external_id == str(uid),
        )
        .limit(1)
    ).scalar_one_or_none()
    if not ident:
        return {"membership_id": membership_id, "group_ids": [], "role": role, "audience": audience, "portal_user_id": uid}
    membership = db.execute(
        select(AccountMembership)
        .where(
            AccountMembership.account_id == int(portal.account_id),
            AccountMembership.user_id == int(ident.user_id),
            AccountMembership.status == "active",
        )
        .limit(1)
    ).scalar_one_or_none()
    if membership:
        membership_id = int(membership.id)
        role = str(membership.role or role)
    group_ids = _kb_group_ids_for_membership(db, membership_id)
    return {"membership_id": membership_id, "group_ids": group_ids, "role": role, "audience": audience, "portal_user_id": uid}


def _kb_group_ids_for_membership(db: Session, membership_id: int | None) -> list[int]:
    if not membership_id:
        return []
    return [
        int(x)
        for x in db.execute(
            select(AccountUserGroupMember.group_id).where(AccountUserGroupMember.membership_id == int(membership_id))
        ).scalars().all()
        if x is not None
    ]


def _next_account_no(db: Session) -> int:
    max_no = db.execute(select(func.max(Account.account_no))).scalar()
    return int(max_no or 100000) + 1


def _list_active_accounts(db: Session, app_user_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        select(AccountMembership, Account)
        .join(Account, Account.id == AccountMembership.account_id)
        .where(
            AccountMembership.user_id == app_user_id,
            AccountMembership.status.in_(["active", "invited"]),
        )
        .order_by(AccountMembership.role.desc(), Account.id.asc())
    ).all()
    items: list[dict[str, Any]] = []
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


def _create_embedded_web_session(
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


def _upsert_bitrix_account_integration(db: Session, *, account_id: int, portal: Portal) -> AccountIntegration:
    domain = str(portal.domain or "").strip().lower()
    integ = db.execute(
        select(AccountIntegration).where(
            AccountIntegration.provider == "bitrix",
            AccountIntegration.external_key == domain,
        )
    ).scalar_one_or_none()
    now = datetime.utcnow()
    if not integ:
        integ = AccountIntegration(
            account_id=int(account_id),
            provider="bitrix",
            status="active",
            external_key=domain,
            portal_id=int(portal.id),
            credentials_json=None,
            created_at=now,
            updated_at=now,
        )
        db.add(integ)
        db.flush()
        return integ
    integ.account_id = int(account_id)
    integ.portal_id = int(portal.id)
    integ.status = "active"
    integ.updated_at = now
    db.add(integ)
    db.flush()
    return integ


def _ensure_portal_can_attach(db: Session, portal: Portal, account_id: int | None = None) -> None:
    if portal.account_id and account_id is not None and int(portal.account_id) == int(account_id):
        return
    if portal.account_id:
        raise HTTPException(status_code=409, detail="portal_already_attached")


def _account_scope_portal_ids(db: Session, portal_id: int) -> list[int]:
    portal = db.get(Portal, int(portal_id))
    if not portal:
        return [int(portal_id)]
    if not portal.account_id:
        return [int(portal_id)]
    rows = db.execute(
        select(Portal.id)
        .where(Portal.account_id == int(portal.account_id))
        .order_by(Portal.id.asc())
    ).scalars().all()
    ids = [int(x) for x in rows if x is not None]
    return ids or [int(portal_id)]


def _kb_storage_portal_id(db: Session, portal_id: int) -> int:
    portal = db.get(Portal, int(portal_id))
    if not portal or not portal.account_id:
        return int(portal_id)
    integrations = db.execute(
        select(AccountIntegration)
        .where(AccountIntegration.account_id == int(portal.account_id))
        .where(AccountIntegration.provider == "bitrix")
        .where(AccountIntegration.status == "active")
        .order_by(AccountIntegration.id.asc())
    ).scalars().all()
    for integration in integrations:
        meta = dict(integration.credentials_json or {})
        if meta.get("is_primary") and integration.portal_id:
            return int(integration.portal_id)
    ids = _account_scope_portal_ids(db, int(portal_id))
    return int(ids[0]) if ids else int(portal_id)


def _account_scoped_file(db: Session, portal_id: int, file_id: int) -> KBFile | None:
    portal = db.get(Portal, int(portal_id))
    if portal and portal.account_id:
        return db.execute(
            select(KBFile).where(
                KBFile.id == int(file_id),
                sa.or_(
                    KBFile.account_id == int(portal.account_id),
                    sa.and_(KBFile.account_id.is_(None), KBFile.portal_id.in_(_account_scope_portal_ids(db, portal_id))),
                ),
            )
        ).scalar_one_or_none()
    scope_portal_ids = _account_scope_portal_ids(db, portal_id)
    return db.execute(
        select(KBFile).where(KBFile.id == int(file_id), KBFile.portal_id.in_(scope_portal_ids))
    ).scalar_one_or_none()


def _account_scoped_collection(db: Session, portal_id: int, collection_id: int) -> KBCollection | None:
    portal = db.get(Portal, int(portal_id))
    if portal and portal.account_id:
        return db.execute(
            select(KBCollection).where(
                KBCollection.id == int(collection_id),
                sa.or_(
                    KBCollection.account_id == int(portal.account_id),
                    sa.and_(KBCollection.account_id.is_(None), KBCollection.portal_id.in_(_account_scope_portal_ids(db, portal_id))),
                ),
            )
        ).scalar_one_or_none()
    scope_portal_ids = _account_scope_portal_ids(db, portal_id)
    return db.execute(select(KBCollection).where(KBCollection.id == int(collection_id), KBCollection.portal_id.in_(scope_portal_ids))).scalar_one_or_none()


def _account_scoped_smart_folder(db: Session, portal_id: int, folder_id: int) -> KBSmartFolder | None:
    portal = db.get(Portal, int(portal_id))
    if portal and portal.account_id:
        return db.execute(
            select(KBSmartFolder).where(
                KBSmartFolder.id == int(folder_id),
                sa.or_(
                    KBSmartFolder.account_id == int(portal.account_id),
                    sa.and_(KBSmartFolder.account_id.is_(None), KBSmartFolder.portal_id.in_(_account_scope_portal_ids(db, portal_id))),
                ),
            )
        ).scalar_one_or_none()
    scope_portal_ids = _account_scope_portal_ids(db, portal_id)
    return db.execute(select(KBSmartFolder).where(KBSmartFolder.id == int(folder_id), KBSmartFolder.portal_id.in_(scope_portal_ids))).scalar_one_or_none()


def _account_scoped_kb_folder(db: Session, portal_id: int, folder_id: int) -> KBFolder | None:
    portal = db.get(Portal, int(portal_id))
    if portal and portal.account_id:
        return db.execute(
            select(KBFolder).where(
                KBFolder.id == int(folder_id),
                sa.or_(
                    KBFolder.account_id == int(portal.account_id),
                    sa.and_(KBFolder.account_id.is_(None), KBFolder.portal_id.in_(_account_scope_portal_ids(db, portal_id))),
                ),
            )
        ).scalar_one_or_none()
    scope_portal_ids = _account_scope_portal_ids(db, portal_id)
    return db.execute(select(KBFolder).where(KBFolder.id == int(folder_id), KBFolder.portal_id.in_(scope_portal_ids))).scalar_one_or_none()


def _ensure_kb_root_folders(db: Session, portal_id: int) -> dict[str, KBFolder]:
    portal = db.get(Portal, int(portal_id))
    owner_portal_id = _kb_storage_portal_id(db, portal_id)
    if portal and portal.account_id:
        scope_filter = sa.or_(
            KBFolder.account_id == int(portal.account_id),
            sa.and_(KBFolder.account_id.is_(None), KBFolder.portal_id.in_(_account_scope_portal_ids(db, portal_id))),
        )
    else:
        scope_filter = KBFolder.portal_id.in_(_account_scope_portal_ids(db, portal_id))

    rows = db.execute(
        select(KBFolder)
        .where(scope_filter)
        .where(KBFolder.parent_id.is_(None))
        .order_by(KBFolder.id.asc())
    ).scalars().all()

    by_space: dict[str, KBFolder] = {}
    for row in rows:
        space = str(row.root_space or "").strip().lower()
        if space in KB_ROOT_SPACE_LABELS and space not in by_space:
            by_space[space] = row

    def _matches_root_name(folder_name: str, space: str) -> bool:
        value = str(folder_name or "").strip().lower()
        if not value:
            return False
        if space == "shared":
            return "общ" in value or "shared" in value
        if space == "departments":
            return "отдел" in value or "department" in value
        if space == "clients":
            return "клиент" in value or "client" in value
        return False

    changed = False
    for space in KB_ROOT_SPACE_LABELS:
        if space in by_space:
            continue
        for row in rows:
            if row.root_space:
                continue
            if _matches_root_name(row.name, space):
                row.root_space = space
                row.updated_at = datetime.utcnow()
                db.add(row)
                by_space[space] = row
                changed = True
                break

    for space, label in KB_ROOT_SPACE_LABELS.items():
        if space in by_space:
            continue
        rec = KBFolder(
            account_id=int(portal.account_id) if portal and portal.account_id else None,
            portal_id=owner_portal_id,
            parent_id=None,
            root_space=space,
            name=label,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(rec)
        db.flush()
        by_space[space] = rec
        changed = True
    if changed:
        db.commit()
    return by_space


def _kb_folder_root_space(folder: KBFolder, folder_map: dict[int, KBFolder]) -> str | None:
    current = folder
    visited: set[int] = set()
    while current and int(current.id) not in visited:
        visited.add(int(current.id))
        space = str(current.root_space or "").strip().lower()
        if space in KB_ROOT_SPACE_LABELS:
            return space
        if current.parent_id is None:
            return None
        parent = folder_map.get(int(current.parent_id))
        if not parent:
            return None
        current = parent
    return None


def _acl_items_payload(rows: list[Any]) -> list[dict[str, str]]:
    return [
        {
            "principal_type": str(getattr(row, "principal_type", "") or ""),
            "principal_id": str(getattr(row, "principal_id", "") or ""),
            "access_level": str(getattr(row, "access_level", "none") or "none"),
        }
        for row in rows
    ]


def _replace_folder_acl(db: Session, folder_id: int, items: list[ACLItemBody]) -> list[dict[str, str]]:
    db.execute(delete(KBFolderAccess).where(KBFolderAccess.folder_id == int(folder_id)))
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        ptype, pid = normalize_kb_principal(item.principal_type, item.principal_id)
        level = str(item.access_level or "read").strip().lower()
        if level not in KB_ACCESS_LEVELS:
            raise ValueError("invalid_access_level")
        key = (ptype, pid)
        if key in seen:
            continue
        seen.add(key)
        db.add(KBFolderAccess(folder_id=int(folder_id), principal_type=ptype, principal_id=pid, access_level=level))
        out.append({"principal_type": ptype, "principal_id": pid, "access_level": level})
    return out


def _replace_file_acl(db: Session, file_id: int, items: list[ACLItemBody]) -> list[dict[str, str]]:
    db.execute(delete(KBFileAccess).where(KBFileAccess.file_id == int(file_id)))
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        ptype, pid = normalize_kb_principal(item.principal_type, item.principal_id)
        level = str(item.access_level or "read").strip().lower()
        if level not in KB_ACCESS_LEVELS:
            raise ValueError("invalid_access_level")
        key = (ptype, pid)
        if key in seen:
            continue
        seen.add(key)
        db.add(KBFileAccess(file_id=int(file_id), principal_type=ptype, principal_id=pid, access_level=level))
        out.append({"principal_type": ptype, "principal_id": pid, "access_level": level})
    return out


def _build_bitrix_attachable_accounts(db: Session, web_user: WebUser) -> list[BitrixPortalAttachAccountItem]:
    email = (web_user.email or "").strip().lower()
    if not email:
        return []
    cred = db.execute(select(AppUserWebCredential).where(AppUserWebCredential.email == email)).scalar_one_or_none()
    if not cred:
        return []

    rows = db.execute(
        select(AccountMembership, Account, AccountPermission)
        .join(Account, Account.id == AccountMembership.account_id)
        .join(AccountPermission, AccountPermission.membership_id == AccountMembership.id, isouter=True)
        .where(AccountMembership.user_id == int(cred.user_id))
        .where(AccountMembership.status == "active")
        .order_by(Account.account_no.asc().nullslast(), Account.id.asc())
    ).all()

    items: list[BitrixPortalAttachAccountItem] = []
    for membership, account, perm in rows:
        role = str(membership.role or "member")
        can_manage_integrations = role in {"owner", "admin"} or bool(
            perm.can_manage_settings if perm else False
        )
        policy = get_account_effective_policy(db, int(account.id))
        bitrix_limit = int((policy.get("limits") or {}).get("max_bitrix_portals") or 0)
        attach_allowed = can_manage_integrations and not is_account_bitrix_portal_limit_reached(
            db,
            int(account.id),
            extra_portals=1,
        )
        reason = None
        if not can_manage_integrations:
            reason = "insufficient_role"
        elif bitrix_limit > 0 and not attach_allowed:
            reason = "bitrix_portal_limit_reached"

        items.append(
            BitrixPortalAttachAccountItem(
                account_id=int(account.id),
                account_no=int(account.account_no) if account.account_no is not None else None,
                name=account.name or f"Account #{account.id}",
                slug=account.slug,
                role=role,
                can_manage_integrations=can_manage_integrations,
                attach_allowed=attach_allowed,
                reason=reason,
                bitrix_portals_used=get_account_bitrix_portal_count(db, int(account.id)),
                bitrix_portals_limit=bitrix_limit,
            )
        )
    return items


def _portal_product_gates(db: Session, portal_id: int) -> tuple[dict[str, Any], dict[str, Any], Portal | None]:
    portal = db.get(Portal, portal_id)
    policy = get_portal_effective_policy(db, portal_id)
    features = dict(policy.get("features") or {})

    def gate(flag: str) -> dict[str, Any]:
        allowed = bool(features.get(flag, False))
        return {
            "allowed": allowed,
            "reason": "" if allowed else "not_in_plan",
        }

    gates = {
        "client_bot": gate("allow_client_bot"),
        "amocrm_integration": gate("allow_amocrm_integration"),
        "webhooks": gate("allow_webhooks"),
        "bitrix_integration": gate("allow_bitrix_integration"),
    }
    return gates, policy, portal


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


def _file_sig_payload(portal_id: int, file_id: int, exp: int, inline: int, rendition: str = "original") -> str:
    return f"{int(portal_id)}:{int(file_id)}:{int(exp)}:{int(inline)}:{(rendition or 'original').strip().lower()}"


def _make_file_sig(portal_id: int, file_id: int, exp: int, inline: int, rendition: str = "original") -> str:
    s = get_settings()
    key = (s.jwt_secret or s.secret_key or "dev-secret-change-in-production").encode("utf-8")
    payload = _file_sig_payload(portal_id, file_id, exp, inline, rendition).encode("utf-8")
    return hmac.new(key, payload, digestmod="sha256").hexdigest()


def _backfill_chunk_pages_from_preview(db: Session, rec: KBFile, preview_pdf_path: str) -> None:
    """Fill missing page_num for existing chunks using preview PDF text matching."""
    if not preview_pdf_path or not os.path.exists(preview_pdf_path):
        return
    rows = db.execute(
        select(KBChunk)
        .where(KBChunk.file_id == rec.id)
        .order_by(KBChunk.chunk_index.asc())
    ).scalars().all()
    if not rows:
        return
    if all((r.page_num is not None and int(r.page_num) > 0) for r in rows):
        return
    try:
        from apps.backend.services.kb_ingest import _assign_chunk_pages_from_preview  # type: ignore
        _assign_chunk_pages_from_preview(rows, preview_pdf_path)
        db.add_all(rows)
        db.commit()
    except Exception:
        db.rollback()


def _content_disposition(filename: str, inline: bool) -> str:
    disp = "inline" if inline else "attachment"
    ascii_fallback = "".join(ch if ord(ch) < 128 else "_" for ch in (filename or "file"))
    encoded = quote(filename or "file")
    return f"{disp}; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded}"


def _err(request: Request | None, code: str, message: str, status_code: int, detail: str | None = None):
    return JSONResponse(
        error_envelope(
            code=code,
            message=message,
            trace_id=_trace_id(request) if request else "",
            detail=detail,
            legacy_error=True,
        ),
        status_code=status_code,
    )


def _log_kb_ask_rag_debug(
    db: Session,
    trace_id: str,
    portal_id: int,
    path: str,
    rag_debug: dict[str, Any] | None,
) -> None:
    if not trace_id or not isinstance(rag_debug, dict):
        return
    summary = {
        "rag_debug": rag_debug,
        "event": "kb_ask_rag_debug",
    }
    row = BitrixHttpLog(
        trace_id=trace_id,
        portal_id=portal_id,
        direction="internal",
        kind="kb_ask_rag_debug",
        method="POST",
        path=path,
        summary_json=json.dumps(summary),
        status_code=200,
        latency_ms=0,
    )
    db.add(row)
    db.commit()


def _portal_user_id_from_token(request: Request) -> int | None:
    auth = request.headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except Exception:
        return None
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
        or auth.get("AUTH_ID")
        or auth.get("access_token")
        or auth.get("ACCESS_TOKEN")
        or auth.get("auth_id")
    )
    refresh_token = (
        merged.get("REFRESH_ID")
        or auth.get("REFRESH_ID")
        or auth.get("refresh_token")
        or auth.get("REFRESH_TOKEN")
        or auth.get("refresh_id")
    )
    domain = merged.get("DOMAIN") or auth.get("domain") or auth.get("DOMAIN")
    member_id = str(merged.get("MEMBER_ID") or auth.get("member_id") or auth.get("MEMBER_ID") or "")
    app_sid = merged.get("APP_SID") or auth.get("application_token") or auth.get("APP_SID")
    local_client_id = (
        merged.get("local_client_id")
        or auth.get("local_client_id")
        or merged.get("CLIENT_ID")
        or auth.get("CLIENT_ID")
        or merged.get("client_id")
        or auth.get("client_id")
        or merged.get("clientId")
        or auth.get("clientId")
    )
    local_client_secret = (
        merged.get("local_client_secret")
        or auth.get("local_client_secret")
        or merged.get("CLIENT_SECRET")
        or auth.get("CLIENT_SECRET")
        or merged.get("client_secret")
        or auth.get("client_secret")
        or merged.get("clientSecret")
        or auth.get("clientSecret")
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
    return RedirectResponse(url=_install_redirect_url(request), status_code=303)


@router.post("/install/complete")
async def bitrix_install_complete(request: Request, db: Session = Depends(get_db)):
    """API only: вызывайте через fetch из install.html. При document navigation — 303 на /install."""
    tid = _trace_id(request)
    if not _is_install_complete_api_request(request):
        logger.info("install_complete_mode=document_blocked trace_id=%s method=POST", tid)
        return RedirectResponse(url=_install_redirect_url(request), status_code=303)
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
    access_token = (
        merged.get("AUTH_ID")
        or auth.get("AUTH_ID")
        or auth.get("access_token")
        or auth.get("ACCESS_TOKEN")
        or auth.get("auth_id")
    )
    refresh_token = (
        merged.get("REFRESH_ID")
        or auth.get("REFRESH_ID")
        or auth.get("refresh_token")
        or auth.get("REFRESH_TOKEN")
        or auth.get("refresh_id")
    )
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
    local_client_id = (
        merged.get("local_client_id")
        or auth.get("local_client_id")
        or merged.get("CLIENT_ID")
        or auth.get("CLIENT_ID")
        or merged.get("client_id")
        or auth.get("client_id")
        or merged.get("clientId")
        or auth.get("clientId")
    )
    local_client_secret = (
        merged.get("local_client_secret")
        or auth.get("local_client_secret")
        or merged.get("CLIENT_SECRET")
        or auth.get("CLIENT_SECRET")
        or merged.get("client_secret")
        or auth.get("client_secret")
        or merged.get("clientSecret")
        or auth.get("clientSecret")
    )
    domain_clean = _domain_clean(domain)
    portal = db.execute(select(Portal).where(Portal.domain == domain_clean)).scalar_one_or_none()
    if not portal:
        # New install flow may hit session/start before any portal row exists.
        portal = Portal(domain=domain_clean, status="active", install_type="market")
        db.add(portal)
        db.commit()
        db.refresh(portal)
    enc_key = get_settings().token_encryption_key or get_settings().secret_key
    if local_client_id:
        portal.local_client_id = str(local_client_id)
    if local_client_secret and enc_key:
        portal.local_client_secret_encrypted = encrypt_token(str(local_client_secret), enc_key)
    if local_client_id or local_client_secret:
        db.add(portal)
        db.commit()
    log_activity(db, kind="iframe", portal_id=portal.id, web_user_id=None)
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
    web_linked = db.execute(
        select(WebUser.id).where(WebUser.portal_id == portal.id).limit(1)
    ).first() is not None
    portal_token = create_portal_token_with_user(portal.id, user_id, expires_minutes=15)
    return JSONResponse({
        "portal_token": portal_token,
        "portal_id": portal.id,
        "is_portal_admin": is_portal_admin,
        "web_linked": web_linked,
    })


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
        return _err(request, "forbidden", "Forbidden", 403, detail="portal_id mismatch")
    portal = db.execute(select(Portal).where(Portal.id == portal_id)).scalar_one_or_none()
    if not portal:
        return _err(request, "portal_not_found", "Portal not found", 404)
    try:
        access_token = get_valid_access_token(db, portal_id, trace_id=_trace_id(request))
    except BitrixAuthError as e:
        return _err(request, e.code, e.code, 400, detail=e.detail)
    domain_full = f"https://{portal.domain}"
    users_list, err = user_get(domain_full, access_token, start=start, limit=limit)
    if err == "missing_scope_user":
        # After reinstall/scope update Bitrix may still answer with stale token context.
        # Try one forced refresh + one retry before returning missing_scope.
        try:
            try:
                refresh_portal_tokens(db, portal_id, trace_id=_trace_id(request))
            except BitrixAuthError:
                pass
            access_token_retry = get_valid_access_token(db, portal_id, trace_id=_trace_id(request))
            users_list, err = user_get(domain_full, access_token_retry, start=start, limit=limit)
        except BitrixAuthError:
            pass
    if err == "missing_scope_user":
        return _err(
            request,
            "missing_scope_user",
            "missing_scope_user",
            403,
            detail="Не хватает права user. Добавьте право user в приложении Bitrix24 и переустановите.",
        )
    if err:
        return _err(request, "bitrix_users_failed", "bitrix_users_failed", 502, detail=err)
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


class WebAccessUserBody(BaseModel):
    name: str
    telegram_username: str | None = None


class FinalizeInstallBody(BaseModel):
    portal_id: int
    selected_user_ids: list[int]
    auth_context: dict = {}


class LocalBitrixCredentialsBody(BaseModel):
    client_id: str
    client_secret: str


class WebRegisterBody(BaseModel):
    email: EmailStr
    password: str
    company: str | None = None


class WebLinkRequestBody(BaseModel):
    email: EmailStr


class WebLoginBody(BaseModel):
    email: EmailStr
    password: str


class BitrixCreateAccountBody(WebLoginBody):
    account_name: str | None = None


class BitrixAttachExistingBody(WebLoginBody):
    account_id: int


class BitrixPortalAttachAccountItem(BaseModel):
    account_id: int
    account_no: int | None = None
    name: str
    slug: str | None = None
    role: str
    can_manage_integrations: bool
    attach_allowed: bool
    reason: str | None = None
    bitrix_portals_used: int
    bitrix_portals_limit: int


class BitrixPortalLinkPrecheckResponse(BaseModel):
    status: str
    email: str
    portal_id: int
    portal_domain: str | None = None
    same_portal_linked: bool = False
    current_web_portal_id: int | None = None
    can_create_new_account: bool = True
    attachable_accounts: list[BitrixPortalAttachAccountItem]
    recommended_action: str


class CollectionBody(BaseModel):
    name: str | None = None
    color: str | None = None


class CollectionFileBody(BaseModel):
    file_id: int


class SmartFolderBody(BaseModel):
    name: str
    system_tag: str | None = None
    rules_json: dict | None = None


class FolderBody(BaseModel):
    name: str
    parent_id: int | None = None


class FileFolderBody(BaseModel):
    folder_id: int | None = None


KB_ROOT_SPACE_LABELS = {
    "shared": "Общие",
    "departments": "Отделы",
    "clients": "Клиенты",
}


class ACLItemBody(BaseModel):
    principal_type: str
    principal_id: str
    access_level: str = "read"


class ACLListBody(BaseModel):
    items: list[ACLItemBody] = []


class KBAskBody(BaseModel):
    query: str
    audience: str | None = None
    show_sources: bool | None = None
    sources_format: str | None = None
    scope: dict | None = None


def _require_portal_admin(db: Session, portal_id: int, request: Request) -> Portal:
    portal = db.execute(select(Portal).where(Portal.id == portal_id)).scalar_one_or_none()
    if not portal:
        raise HTTPException(status_code=404, detail="Portal not found")
    uid = _portal_user_id_from_token(request)
    if uid and portal.admin_user_id and int(portal.admin_user_id) == int(uid):
        return portal
    # allow web owner for linked portals
    if uid:
        web_user = db.execute(
            select(WebUser).where(WebUser.id == int(uid), WebUser.portal_id == portal_id)
        ).scalar_one_or_none()
        if web_user:
            return portal
    raise HTTPException(status_code=403, detail="Доступ только для администратора портала")
    return portal


def _strip_sources_block(answer: str | None) -> str:
    text = (answer or "").strip()
    marker = "\n\nИсточники:"
    idx = text.find(marker)
    if idx >= 0:
        return text[:idx].rstrip()
    marker2 = "\nИсточники:"
    idx2 = text.find(marker2)
    if idx2 >= 0:
        return text[:idx2].rstrip()
    return text


def _resolve_uploader(db: Session, portal_id: int, request: Request) -> tuple[str | None, str | None, str | None]:
    uid = _portal_user_id_from_token(request)
    if uid is None:
        return None, None, None
    web_user = db.execute(
        select(WebUser).where(WebUser.id == int(uid), WebUser.portal_id == portal_id)
    ).scalar_one_or_none()
    if web_user:
        return "web", str(web_user.id), web_user.email
    access = db.execute(
        select(PortalUsersAccess).where(
            PortalUsersAccess.portal_id == portal_id,
            PortalUsersAccess.user_id == str(uid),
        )
    ).scalar_one_or_none()
    if access:
        return "bitrix", str(uid), access.display_name or f"Bitrix user {uid}"
    return "bitrix", str(uid), f"Bitrix user {uid}"


_KB_TOPICS = [
    {
        "id": "product",
        "name": "\u041f\u0440\u043e\u0434\u0443\u043a\u0442 \u0438 \u0444\u0443\u043d\u043a\u0446\u0438\u043e\u043d\u0430\u043b\u044c\u043d\u043e\u0441\u0442\u044c",
        "keywords": [
            "\u0444\u0443\u043d\u043a\u0446\u0438\u0438", "\u0444\u0443\u043d\u043a\u0446\u0438\u043e\u043d\u0430\u043b", "feature", "\u0432\u043e\u0437\u043c\u043e\u0436\u043d\u043e\u0441\u0442\u0438", "\u043f\u043b\u0430\u0442\u0444\u043e\u0440\u043c\u0430",
            "rag", "\u0431\u0430\u0437\u0430 \u0437\u043d\u0430\u043d\u0438\u0439", "\u043c\u043e\u0434\u0435\u043b\u0438", "\u0438\u043d\u0442\u0435\u0440\u0444\u0435\u0439\u0441",
            "\u043a\u043e\u043d\u0441\u0442\u0440\u0443\u043a\u0442\u043e\u0440", "\u0441\u0446\u0435\u043d\u0430\u0440\u0438\u0439", "\u0447\u0430\u0442-\u0431\u043e\u0442",
        ],
    },
    {
        "id": "pricing",
        "name": "\u0422\u0430\u0440\u0438\u0444\u044b \u0438 \u0446\u0435\u043d\u044b",
        "keywords": [
            "\u0442\u0430\u0440\u0438\u0444", "\u0446\u0435\u043d\u0430", "\u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c", "\u043e\u043f\u043b\u0430\u0442\u0430", "\u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0430", "billing",
            "\u0441\u0447\u0435\u0442", "\u043f\u0440\u0430\u0439\u0441", "invoice",
        ],
    },
    {
        "id": "integrations",
        "name": "\u0418\u043d\u0442\u0435\u0433\u0440\u0430\u0446\u0438\u0438 \u0438 \u043f\u0440\u043e\u0446\u0435\u0441\u0441\u044b",
        "keywords": [
            "\u0438\u043d\u0442\u0435\u0433\u0440\u0430\u0446\u0438\u044f", "\u0438\u043d\u0442\u0435\u0433\u0440\u0430\u0446\u0438\u0438", "crm", "bitrix", "\u0431\u0438\u0442\u0440\u0438\u043a\u0441", "amo",
            "webhook", "api", "oauth", "telegram",
        ],
    },
    {
        "id": "sales",
        "name": "\u041f\u0440\u043e\u0434\u0430\u0436\u0438 \u0438 \u043a\u0432\u0430\u043b\u0438\u0444\u0438\u043a\u0430\u0446\u0438\u044f",
        "keywords": [
            "\u043f\u0440\u043e\u0434\u0430\u0436", "\u043b\u0438\u0434", "\u0432\u043e\u0440\u043e\u043d\u043a\u0430", "\u0441\u0434\u0435\u043b\u043a", "\u043a\u043e\u043d\u0432\u0435\u0440\u0441\u0438\u044f",
            "qualification", "offer", "objection", "cta",
        ],
    },
    {
        "id": "support",
        "name": "\u041f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430 \u0438 \u0441\u0435\u0440\u0432\u0438\u0441",
        "keywords": [
            "\u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a", "\u0438\u043d\u0446\u0438\u0434\u0435\u043d\u0442", "\u043e\u0448\u0438\u0431\u043a", "\u0442\u0438\u043a\u0435\u0442",
            "sla", "support", "\u0441\u0435\u0440\u0432\u0438\u0441", "\u043f\u043e\u043c\u043e\u0449",
        ],
    },
    {
        "id": "hr",
        "name": "HR \u0438 \u043a\u043e\u043c\u0430\u043d\u0434\u0430",
        "keywords": [
            "\u0441\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u043a", "\u043a\u043e\u043c\u0430\u043d\u0434", "\u043d\u0430\u0439\u043c", "\u0432\u0430\u043a\u0430\u043d\u0441", "hr",
            "\u043e\u043d\u0431\u043e\u0440\u0434\u0438\u043d\u0433", "\u043e\u0431\u0443\u0447\u0435\u043d\u0438\u0435",
        ],
    },
    {
        "id": "analytics",
        "name": "\u0410\u043d\u0430\u043b\u0438\u0442\u0438\u043a\u0430 \u0438 \u043c\u0435\u0442\u0440\u0438\u043a\u0438",
        "keywords": [
            "\u0430\u043d\u0430\u043b\u0438\u0442\u0438\u043a", "\u043e\u0442\u0447\u0435\u0442", "\u043c\u0435\u0442\u0440\u0438\u043a", "retention",
            "ret3", "dashboard", "\u043a\u043e\u0433\u043e\u0440\u0442", "\u0441\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a",
        ],
    },
]

def _topic_matches(text: str, keywords: list[str]) -> bool:
    t = (text or "").lower()
    if not t:
        return False
    return any(k in t for k in keywords)


def _make_chunk_anchor(
    chunk_index: int | None,
    page_num: int | None,
    start_ms: int | None,
) -> tuple[str, str]:
    if page_num is not None and int(page_num) > 0:
        return "pdf_page", str(int(page_num))
    if start_ms is not None and int(start_ms) >= 0:
        return "media_ms", str(int(start_ms))
    if chunk_index is not None and int(chunk_index) >= 0:
        return "chunk_index", str(int(chunk_index))
    return "chunk_index", "0"


_MEDIA_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}


def _is_media_file(filename: str | None, mime_type: str | None) -> bool:
    ext = os.path.splitext((filename or "").lower())[1]
    mt = (mime_type or "").lower().strip()
    return ext in _MEDIA_EXTS or mt.startswith("audio/") or mt.startswith("video/")


def _estimate_media_minutes(src_path: str) -> int:
    try:
        from apps.backend.services.kb_ingest import _media_duration_seconds  # type: ignore

        seconds = int(_media_duration_seconds(src_path) or 0)
        if seconds <= 0:
            return 1
        return max(1, int(math.ceil(seconds / 60.0)))
    except Exception:
        return 1


def _diarization_runtime_status() -> tuple[bool, str]:
    def _has_module(name: str) -> bool:
        try:
            return importlib.util.find_spec(name) is not None
        except Exception:
            return False

    enabled = (os.getenv("ENABLE_SPEAKER_DIARIZATION") or "").strip().lower() in ("1", "true", "yes", "on")
    if not enabled:
        return False, "disabled_by_env"
    token = (os.getenv("PYANNOTE_TOKEN") or os.getenv("HUGGINGFACE_TOKEN") or "").strip()
    if not token:
        return False, "missing_token"
    # Диаризация выполняется в worker-ingest, а не в backend-контейнере.
    # Здесь проверяем только флаги доступа.
    return True, "ok"


def _parse_csv_ints(raw: str | None) -> list[int]:
    if not raw:
        return []
    out: list[int] = []
    for p in str(raw).split(","):
        v = p.strip()
        if not v:
            continue
        try:
            iv = int(v)
        except Exception:
            continue
        if iv > 0:
            out.append(iv)
    return sorted(set(out))


def _resolve_scope_file_ids(
    db: Session,
    *,
    portal_id: int,
    audience: str,
    file_ids: list[int] | None = None,
    collection_ids: list[int] | None = None,
    smart_folder_ids: list[int] | None = None,
    topic_ids: list[str] | None = None,
) -> set[int] | None:
    scope_portal_ids = _account_scope_portal_ids(db, portal_id)
    scopes: list[set[int]] = []
    portal = db.get(Portal, int(portal_id))
    file_scope_predicate = (
        sa.or_(
            KBFile.account_id == int(portal.account_id),
            sa.and_(KBFile.account_id.is_(None), KBFile.portal_id.in_(scope_portal_ids)),
        )
        if portal and portal.account_id
        else KBFile.portal_id.in_(scope_portal_ids)
    )
    folder_scope_predicate = (
        sa.or_(
            KBSmartFolder.account_id == int(portal.account_id),
            sa.and_(KBSmartFolder.account_id.is_(None), KBSmartFolder.portal_id.in_(scope_portal_ids)),
        )
        if portal and portal.account_id
        else KBSmartFolder.portal_id.in_(scope_portal_ids)
    )
    ids_file = {int(x) for x in (file_ids or []) if int(x) > 0}
    if ids_file:
        allowed = {
            int(x)
            for x in db.execute(
                select(KBFile.id).where(
                    file_scope_predicate,
                    KBFile.audience == audience,
                    KBFile.id.in_(sorted(ids_file)),
                )
            ).scalars().all()
        }
        scopes.append(allowed)
    col_ids = [int(x) for x in (collection_ids or []) if int(x) > 0]
    if col_ids:
        col_set = {
            int(x)
            for x in db.execute(
                select(KBCollectionFile.file_id)
                .join(KBFile, KBFile.id == KBCollectionFile.file_id)
                .where(
                    KBCollectionFile.collection_id.in_(col_ids),
                    file_scope_predicate,
                    KBFile.audience == audience,
                )
            ).scalars().all()
        }
        scopes.append(col_set)
    smart_ids = [int(x) for x in (smart_folder_ids or []) if int(x) > 0]
    if smart_ids:
        rows = db.execute(
            select(KBSmartFolder.id, KBSmartFolder.name, KBSmartFolder.system_tag, KBSmartFolder.rules_json)
            .where(folder_scope_predicate, KBSmartFolder.id.in_(smart_ids))
        ).all()
        topic_keys: set[str] = set()
        for _sid, name, system_tag, rules_json in rows:
            rules = rules_json or {}
            topic = (
                str(system_tag or "").strip()
                or str(rules.get("topic_id") or "").strip()
                or str(rules.get("topic") or "").strip()
                or str(name or "").strip()
            )
            if topic:
                topic_keys.add(topic.lower())
        if topic_keys:
            trows = db.execute(
                select(KBFile.id, KBFile.filename, KBChunk.text)
                .join(KBChunk, KBChunk.file_id == KBFile.id)
                .where(file_scope_predicate, KBFile.audience == audience)
                .limit(8000)
            ).all()
            hit_ids: set[int] = set()
            for fid, fname, txt in trows:
                hay = f"{fname or ''} {txt or ''}".lower()
                matched = False
                for t in _KB_TOPICS:
                    k = str(t["id"]).lower()
                    n = str(t["name"]).lower()
                    if k in topic_keys or n in topic_keys:
                        if _topic_matches(hay, t["keywords"]):
                            matched = True
                            break
                if not matched:
                    for key in topic_keys:
                        if key and key in hay:
                            matched = True
                            break
                if matched:
                    hit_ids.add(int(fid))
            scopes.append(hit_ids)
    tids = [str(x).strip().lower() for x in (topic_ids or []) if str(x).strip()]
    if tids:
        trows = db.execute(
            select(KBFile.id, KBFile.filename, KBChunk.text)
            .join(KBChunk, KBChunk.file_id == KBFile.id)
            .where(file_scope_predicate, KBFile.audience == audience)
            .limit(8000)
        ).all()
        hit_ids: set[int] = set()
        for fid, fname, txt in trows:
            hay = f"{fname or ''} {txt or ''}".lower()
            matched = False
            for t in _KB_TOPICS:
                k = str(t["id"]).lower()
                n = str(t["name"]).lower()
                if k in tids or n in tids:
                    if _topic_matches(hay, t["keywords"]):
                        matched = True
                        break
            if not matched:
                for key in tids:
                    if key and key in hay:
                        matched = True
                        break
            if matched:
                hit_ids.add(int(fid))
        scopes.append(hit_ids)
    if not scopes:
        return None
    out = scopes[0].copy()
    for s in scopes[1:]:
        out &= s
    return out


def _all_account_scope_file_ids(
    db: Session,
    *,
    portal_id: int,
    audience: str,
) -> set[int]:
    portal = db.get(Portal, int(portal_id))
    if portal and portal.account_id:
        rows = db.execute(
            select(KBFile.id)
            .where(
                sa.or_(
                    KBFile.account_id == int(portal.account_id),
                    sa.and_(KBFile.account_id.is_(None), KBFile.portal_id.in_(_account_scope_portal_ids(db, portal_id))),
                )
            )
            .where(KBFile.audience == audience)
            .where(KBFile.status == "ready")
        ).scalars().all()
    else:
        scope_portal_ids = _account_scope_portal_ids(db, portal_id)
        rows = db.execute(
            select(KBFile.id)
            .where(KBFile.portal_id.in_(scope_portal_ids))
            .where(KBFile.audience == audience)
            .where(KBFile.status == "ready")
        ).scalars().all()
    return {int(x) for x in rows if x is not None}


def _filter_file_ids_by_kb_acl(
    db: Session,
    *,
    file_ids: set[int],
    membership_id: int | None,
    group_ids: list[int] | None,
    role: str | None,
    audience: str | None,
) -> set[int]:
    if not file_ids:
        return set()
    rows = db.execute(
        select(KBFile.id, KBFile.folder_id).where(KBFile.id.in_(sorted(file_ids)))
    ).all()
    folder_ids = sorted({int(folder_id) for _fid, folder_id in rows if folder_id is not None})
    file_acl_rows = db.execute(
        select(KBFileAccess.file_id, KBFileAccess.principal_type, KBFileAccess.principal_id, KBFileAccess.access_level)
        .where(KBFileAccess.file_id.in_(sorted(file_ids)))
    ).all()
    folder_acl_rows = []
    if folder_ids:
        folder_acl_rows = db.execute(
            select(KBFolderAccess.folder_id, KBFolderAccess.principal_type, KBFolderAccess.principal_id, KBFolderAccess.access_level)
            .where(KBFolderAccess.folder_id.in_(folder_ids))
        ).all()
    principals = kb_acl_principals_for_membership(membership_id, role, audience, group_ids)
    file_acl_map: dict[int, list[tuple[str, str, str]]] = {}
    for file_id, principal_type, principal_id, access_level in file_acl_rows:
        file_acl_map.setdefault(int(file_id), []).append(
            (str(principal_type), str(principal_id), str(access_level))
        )
    folder_acl_map: dict[int, list[tuple[str, str, str]]] = {}
    for folder_id, principal_type, principal_id, access_level in folder_acl_rows:
        folder_acl_map.setdefault(int(folder_id), []).append(
            (str(principal_type), str(principal_id), str(access_level))
        )
    allowed: set[int] = set()
    for file_id, folder_id in rows:
        inherited = default_kb_access_for_role(role)
        if folder_id is not None:
            inherited = resolve_kb_acl_access(
                folder_acl_map.get(int(folder_id), []),
                principals,
                inherited,
            )
        effective = resolve_kb_acl_access(
            file_acl_map.get(int(file_id), []),
            principals,
            inherited,
        )
        if effective in {"read", "write", "admin"}:
            allowed.add(int(file_id))
    return allowed


def _file_has_kb_acl_access(
    db: Session,
    *,
    file_rec: KBFile,
    membership_id: int | None,
    group_ids: list[int] | None,
    role: str | None,
    audience: str | None,
) -> bool:
    return int(file_rec.id) in _filter_file_ids_by_kb_acl(
        db,
        file_ids={int(file_rec.id)},
        membership_id=membership_id,
        group_ids=group_ids,
        role=role,
        audience=audience or str(file_rec.audience or "staff"),
    )


def _kb_folder_subtree_ids(db: Session, portal_id: int, folder_id: int) -> set[int]:
    portal = db.get(Portal, int(portal_id))
    if portal and portal.account_id:
        folder_rows = db.execute(
            select(KBFolder.id, KBFolder.parent_id).where(
                sa.or_(
                    KBFolder.account_id == int(portal.account_id),
                    sa.and_(KBFolder.account_id.is_(None), KBFolder.portal_id.in_(_account_scope_portal_ids(db, portal_id))),
                )
            )
        ).all()
    else:
        folder_rows = db.execute(
            select(KBFolder.id, KBFolder.parent_id).where(KBFolder.portal_id.in_(_account_scope_portal_ids(db, portal_id)))
        ).all()
    children: dict[int, list[int]] = {}
    ids_present = {int(fid) for fid, _pid in folder_rows if fid is not None}
    for fid, parent_id in folder_rows:
        if parent_id is None:
            continue
        children.setdefault(int(parent_id), []).append(int(fid))
    if int(folder_id) not in ids_present:
        return set()
    out: set[int] = set()
    stack = [int(folder_id)]
    while stack:
        current = stack.pop()
        if current in out:
            continue
        out.add(current)
        stack.extend(children.get(current, []))
    return out


def _kb_client_access_summary(db: Session, portal_id: int, folder_id: int | None = None) -> dict[str, int]:
    portal = db.get(Portal, int(portal_id))
    scope_portal_ids = _account_scope_portal_ids(db, portal_id)
    if portal and portal.account_id:
        file_rows = db.execute(
            select(KBFile.id, KBFile.folder_id).where(
                sa.or_(
                    KBFile.account_id == int(portal.account_id),
                    sa.and_(KBFile.account_id.is_(None), KBFile.portal_id.in_(scope_portal_ids)),
                ),
                KBFile.status == "ready",
            )
        ).all()
        client_group_ids = db.execute(
            select(AccountUserGroup.id).where(
                AccountUserGroup.account_id == int(portal.account_id),
                AccountUserGroup.kind == "client",
            )
        ).scalars().all()
    else:
        file_rows = db.execute(
            select(KBFile.id, KBFile.folder_id).where(
                KBFile.portal_id.in_(scope_portal_ids),
                KBFile.status == "ready",
            )
        ).all()
        client_group_ids = []

    if folder_id is not None:
        subtree_ids = _kb_folder_subtree_ids(db, portal_id, int(folder_id))
        file_rows = [(file_id, current_folder_id) for file_id, current_folder_id in file_rows if current_folder_id is not None and int(current_folder_id) in subtree_ids]

    file_ids = [int(file_id) for file_id, _folder_id in file_rows]
    folder_ids = sorted({int(folder_id) for _file_id, folder_id in file_rows if folder_id is not None})
    file_acl_rows = db.execute(
        select(KBFileAccess.file_id, KBFileAccess.principal_type, KBFileAccess.principal_id, KBFileAccess.access_level)
        .where(KBFileAccess.file_id.in_(file_ids))
    ).all() if file_ids else []
    folder_acl_rows = db.execute(
        select(KBFolderAccess.folder_id, KBFolderAccess.principal_type, KBFolderAccess.principal_id, KBFolderAccess.access_level)
        .where(KBFolderAccess.folder_id.in_(folder_ids))
    ).all() if folder_ids else []

    file_acl_map: dict[int, list[tuple[str, str, str]]] = {}
    for file_id, principal_type, principal_id, access_level in file_acl_rows:
        file_acl_map.setdefault(int(file_id), []).append((str(principal_type), str(principal_id), str(access_level or "none")))
    folder_acl_map: dict[int, list[tuple[str, str, str]]] = {}
    for folder_id, principal_type, principal_id, access_level in folder_acl_rows:
        folder_acl_map.setdefault(int(folder_id), []).append((str(principal_type), str(principal_id), str(access_level or "none")))

    allowed_levels = {"read", "write", "admin"}
    generic_principals = kb_acl_principals_for_membership(None, "client", "client", [])
    open_all_clients = 0
    open_client_groups = 0
    closed_for_clients = 0

    for file_id, folder_id in file_rows:
        inherited_generic = default_kb_access_for_role("client")
        if folder_id is not None:
            inherited_generic = resolve_kb_acl_access(folder_acl_map.get(int(folder_id), []), generic_principals, inherited_generic)
        generic_effective = resolve_kb_acl_access(file_acl_map.get(int(file_id), []), generic_principals, inherited_generic)
        if generic_effective in allowed_levels:
            open_all_clients += 1
            continue

        group_allowed = False
        for group_id in client_group_ids:
            group_principals = kb_acl_principals_for_membership(None, "client", "client", [int(group_id)])
            inherited_group = default_kb_access_for_role("client")
            if folder_id is not None:
                inherited_group = resolve_kb_acl_access(folder_acl_map.get(int(folder_id), []), group_principals, inherited_group)
            group_effective = resolve_kb_acl_access(file_acl_map.get(int(file_id), []), group_principals, inherited_group)
            if group_effective in allowed_levels:
                group_allowed = True
                break

        if group_allowed:
            open_client_groups += 1
        else:
            closed_for_clients += 1

    return {
        "total_ready_files": len(file_rows),
        "open_all_clients": open_all_clients,
        "open_client_groups": open_client_groups,
        "closed_for_clients": closed_for_clients,
    }


def _kb_file_access_badges(db: Session, file_rec: KBFile) -> dict[str, str]:
    folder_access_rows = []
    if file_rec.folder_id:
        folder_access_rows = db.execute(
            select(KBFolderAccess.principal_type, KBFolderAccess.principal_id, KBFolderAccess.access_level)
            .where(KBFolderAccess.folder_id == int(file_rec.folder_id))
        ).all()
    file_access_rows = db.execute(
        select(KBFileAccess.principal_type, KBFileAccess.principal_id, KBFileAccess.access_level)
        .where(KBFileAccess.file_id == int(file_rec.id))
    ).all()
    folder_rules = [(str(pt), str(pid), str(level or "none")) for pt, pid, level in folder_access_rows]
    file_rules = [(str(pt), str(pid), str(level or "none")) for pt, pid, level in file_access_rows]

    staff_principals = kb_acl_principals_for_membership(None, "member", "staff", [])
    client_principals = kb_acl_principals_for_membership(None, "client", "client", [])
    staff_base = default_kb_access_for_role("member")
    client_base = default_kb_access_for_role("client")
    if file_rec.folder_id:
        staff_base = resolve_kb_acl_access(folder_rules, staff_principals, staff_base)
        client_base = resolve_kb_acl_access(folder_rules, client_principals, client_base)
    staff_effective = resolve_kb_acl_access(file_rules, staff_principals, staff_base)
    client_effective = resolve_kb_acl_access(file_rules, client_principals, client_base)

    client_group_only = False
    if client_effective not in {"read", "write", "admin"}:
        has_client_group_rule = any(
            principal_type == "group" and access_level in {"read", "write", "admin"}
            for principal_type, _principal_id, access_level in (folder_rules + file_rules)
        )
        if has_client_group_rule:
            client_group_only = True

    if staff_effective in {"write", "admin"}:
        staff_badge = "staff_admin"
    elif staff_effective == "read":
        staff_badge = "staff_read"
    else:
        staff_badge = "staff_none"

    if client_effective in {"read", "write", "admin"}:
        client_badge = "client_all"
    elif client_group_only:
        client_badge = "client_groups"
    else:
        client_badge = "client_none"

    return {"staff": staff_badge, "client": client_badge}


def _kb_folder_access_badges(db: Session, folder_id: int) -> dict[str, str]:
    folder_access_rows = db.execute(
        select(KBFolderAccess.principal_type, KBFolderAccess.principal_id, KBFolderAccess.access_level)
        .where(KBFolderAccess.folder_id == int(folder_id))
    ).all()
    rules = [(str(pt), str(pid), str(level or "none")) for pt, pid, level in folder_access_rows]
    staff_principals = kb_acl_principals_for_membership(None, "member", "staff", [])
    client_principals = kb_acl_principals_for_membership(None, "client", "client", [])
    staff_effective = resolve_kb_acl_access(rules, staff_principals, default_kb_access_for_role("member"))
    client_effective = resolve_kb_acl_access(rules, client_principals, default_kb_access_for_role("client"))
    client_group_only = (
        client_effective not in {"read", "write", "admin"}
        and any(principal_type == "group" and access_level in {"read", "write", "admin"} for principal_type, _pid, access_level in rules)
    )
    if staff_effective in {"write", "admin"}:
        staff_badge = "staff_admin"
    elif staff_effective == "read":
        staff_badge = "staff_read"
    else:
        staff_badge = "staff_none"
    if client_effective in {"read", "write", "admin"}:
        client_badge = "client_all"
    elif client_group_only:
        client_badge = "client_groups"
    else:
        client_badge = "client_none"
    return {"staff": staff_badge, "client": client_badge}


def _acl_guard_file(
    db: Session,
    *,
    file_rec: KBFile | None,
    portal_id: int,
    request: Request,
    fallback_audience: str = "staff",
) -> KBFile | None:
    if not file_rec:
        return None
    acl_ctx = _portal_acl_subject_ctx(
        db,
        portal_id=portal_id,
        request=request,
        audience=str(file_rec.audience or fallback_audience or "staff"),
    )
    if not _file_has_kb_acl_access(
        db,
        file_rec=file_rec,
        membership_id=acl_ctx.get("membership_id"),
        group_ids=acl_ctx.get("group_ids"),
        role=acl_ctx.get("role"),
        audience=acl_ctx.get("audience"),
    ):
        return None
    return file_rec

def _is_two_part_topic_name(name: str) -> bool:
    n = (name or "").strip().lower()
    if not n:
        return False
    return re.search(r"\b[^\W\d_]+\b\s+и\s+\b[^\W\d_]+\b", n, flags=re.IGNORECASE) is not None


_AUTO_TOPIC_STOPWORDS = {
    "\u0447\u0442\u043e", "\u043a\u0430\u043a", "\u044d\u0442\u043e", "\u0434\u043b\u044f", "\u0438\u043b\u0438", "\u043a\u043e\u0433\u0434\u0430", "\u0433\u0434\u0435", "\u0447\u0442\u043e\u0431\u044b", "\u0435\u0441\u043b\u0438", "\u043f\u0440\u0438",
    "\u0435\u0441\u0442\u044c", "\u043d\u0435\u0442", "\u0431\u044b\u0442\u044c", "\u0431\u0443\u0434\u0435\u0442", "\u043f\u043e\u0441\u043b\u0435", "\u043f\u0435\u0440\u0435\u0434", "\u043c\u0435\u0436\u0434\u0443", "\u043d\u0430\u0434", "\u043f\u043e\u0434",
    "\u043f\u0440\u043e", "also", "with", "from", "into", "your", "ours", "they", "them",
    "\u043a\u043e\u0442\u043e\u0440\u044b\u0439", "\u043a\u043e\u0442\u043e\u0440\u0430\u044f", "\u043a\u043e\u0442\u043e\u0440\u044b\u0435", "\u043a\u043e\u0442\u043e\u0440\u044b\u0445", "\u044d\u0442\u043e\u0442", "\u044d\u0442\u0430", "\u044d\u0442\u0438", "\u0442\u043e\u0433\u043e",
    "\u0432\u0441\u0435\u0433\u043e", "\u0432\u0441\u0435\u0445", "\u043c\u043e\u0436\u043d\u043e", "\u043d\u0443\u0436\u043d\u043e", "\u043e\u0447\u0435\u043d\u044c", "\u0431\u043e\u043b\u0435\u0435", "\u043c\u0435\u043d\u0435\u0435", "\u0442\u0430\u043a\u0436\u0435",
}


def _auto_topic_candidates(
    file_texts: list[tuple[int, str]],
    threshold: int,
    excluded_tokens: set[str],
    limit: int = 8,
) -> list[dict[str, Any]]:
    if not file_texts:
        return []
    token_to_files: dict[str, set[int]] = {}
    for file_id, text in file_texts:
        tokens = set(re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]{4,}", (text or "").lower()))
        for token in tokens:
            if token in _AUTO_TOPIC_STOPWORDS:
                continue
            if token.isdigit():
                continue
            if token in excluded_tokens:
                continue
            if len(token) > 40:
                continue
            token_to_files.setdefault(token, set()).add(int(file_id))
    ranked = sorted(
        ((tok, ids) for tok, ids in token_to_files.items() if len(ids) >= threshold),
        key=lambda x: (-len(x[1]), x[0]),
    )
    out: list[dict[str, Any]] = []
    for tok, ids in ranked[: max(1, limit)]:
        out.append(
            {
                "id": f"auto:{tok}",
                "name": tok.capitalize(),
                "count": len(ids),
                "file_ids": sorted(ids),
                "auto": True,
            }
        )
    return out


@router.post("/portals/{portal_id}/web/register")
async def register_web_from_bitrix(
    request: Request,
    portal_id: int,
    body: WebRegisterBody,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        raise HTTPException(status_code=403, detail="portal_id mismatch")
    portal = _require_portal_admin(db, portal_id, request)
    email = body.email.lower().strip()
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="password_too_short")
    existing = db.execute(select(WebUser).where(WebUser.email == email)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="email_exists")
    user = WebUser(
        email=email,
        password_hash=get_password_hash(body.password),
        portal_id=portal_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(user)
    try:
        meta = json.loads(portal.metadata_json or "{}") if portal.metadata_json else {}
    except Exception:
        meta = {}
    meta["owner_email"] = email
    if body.company:
        meta["company"] = body.company
    portal.metadata_json = json.dumps(meta, ensure_ascii=False)
    db.add(portal)
    ensure_rbac_for_web_user(db, user, force_owner=True, account_name=(body.company or "").strip() or None)
    db.commit()
    token = create_email_token(db, user.id)
    ok, err = send_registration_email(db, user, token)
    if not ok:
        raise HTTPException(status_code=500, detail=err or "email_send_failed")
    return {"status": "confirm_required", "email": user.email}


@router.post("/portals/{portal_id}/web/link/request")
async def request_web_link(
    request: Request,
    portal_id: int,
    body: WebLinkRequestBody,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        raise HTTPException(status_code=403, detail="portal_id mismatch")
    _require_portal_admin(db, portal_id, request)
    raise HTTPException(status_code=410, detail="legacy_link_flow_removed")


@router.get("/portals/{portal_id}/web/status")
async def get_web_link_status(
    request: Request,
    portal_id: int,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        raise HTTPException(status_code=403, detail="portal_id mismatch")
    _require_portal_admin(db, portal_id, request)
    portal = db.get(Portal, portal_id)
    user = _resolve_linked_web_user(db, portal)
    if not user:
        return {
            "linked": False,
            "portal_id": int(portal_id),
            "portal_domain": portal.domain if portal else None,
            "account_id": int(portal.account_id) if portal and portal.account_id else None,
        }
    demo_until = (user.created_at + timedelta(days=7)).date().isoformat()
    account = db.get(Account, int(portal.account_id)) if portal and portal.account_id else None
    return {
        "linked": True,
        "email": user.email,
        "demo_until": demo_until,
        "portal_id": int(portal_id),
        "portal_domain": portal.domain if portal else None,
        "account_id": int(portal.account_id) if portal and portal.account_id else None,
        "account_name": account.name if account else None,
        "account_no": int(account.account_no) if account and account.account_no else None,
    }


@router.post("/portals/{portal_id}/web/link/precheck", response_model=BitrixPortalLinkPrecheckResponse)
async def precheck_web_link_from_bitrix(
    request: Request,
    portal_id: int,
    body: WebLoginBody,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        raise HTTPException(status_code=403, detail="portal_id mismatch")
    _require_portal_admin(db, portal_id, request)
    portal = db.get(Portal, portal_id)
    if not portal:
        raise HTTPException(status_code=404, detail="portal_not_found")

    user = _authenticate_web_user_for_bitrix(db, str(body.email), body.password)
    attachable_accounts = _build_bitrix_attachable_accounts(db, user)
    same_portal_linked = bool(user.portal_id and int(user.portal_id) == int(portal_id))

    recommended_action = "create_account"
    if same_portal_linked:
        recommended_action = "already_linked"
    elif any(item.attach_allowed for item in attachable_accounts):
        recommended_action = "attach_existing"
    elif attachable_accounts:
        recommended_action = "upgrade_or_create"

    return BitrixPortalLinkPrecheckResponse(
        status="ok",
        email=(user.email or "").strip().lower(),
        portal_id=int(portal_id),
        portal_domain=portal.domain,
        same_portal_linked=same_portal_linked,
        current_web_portal_id=int(user.portal_id) if user.portal_id else None,
        can_create_new_account=True,
        attachable_accounts=attachable_accounts,
        recommended_action=recommended_action,
    )


@router.post("/portals/{portal_id}/web/link/create-account")
async def create_account_for_bitrix_portal(
    request: Request,
    portal_id: int,
    body: BitrixCreateAccountBody,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        raise HTTPException(status_code=403, detail="portal_id mismatch")
    _require_portal_admin(db, portal_id, request)
    portal = db.get(Portal, portal_id)
    if not portal:
        raise HTTPException(status_code=404, detail="portal_not_found")
    _ensure_portal_can_attach(db, portal)

    user = _authenticate_web_user_for_bitrix(db, str(body.email), body.password)
    now = datetime.utcnow()
    app_user_id = _get_app_user_id_for_web_user(db, user)
    if not app_user_id:
        account_id, app_user_id = ensure_rbac_for_web_user(db, user, force_owner=True)
        if not account_id or not app_user_id:
            raise HTTPException(status_code=400, detail="account_create_failed")
    account = Account(
        account_no=_next_account_no(db),
        name=(body.account_name or portal.domain or "").strip() or None,
        slug=None,
        status="active",
        owner_user_id=int(app_user_id),
        created_at=now,
        updated_at=now,
    )
    db.add(account)
    db.flush()
    account.slug = build_unique_account_slug(
        db,
        account.name or portal.domain or None,
        fallback=f"workspace-{int(account.account_no or account.id)}",
        exclude_account_id=int(account.id),
    )
    db.add(account)
    membership, _created = ensure_account_member(
        db,
        account_id=int(account.id),
        user_id=int(app_user_id),
        role="owner",
        status="active",
        kb_access="write",
        can_invite_users=True,
        can_manage_settings=True,
        can_view_finance=True,
    )
    membership.role = "owner"
    membership.status = "active"
    membership.updated_at = now
    db.add(membership)

    portal.account_id = int(account.id)
    db.add(portal)
    _upsert_bitrix_account_integration(db, account_id=int(account.id), portal=portal)
    db.commit()
    return {
        "status": "linked",
        "action": "create_account",
        "account_id": int(account.id),
        "portal_id": int(portal_id),
    }


@router.post("/portals/{portal_id}/web/link/attach-existing")
async def attach_bitrix_portal_to_existing_account(
    request: Request,
    portal_id: int,
    body: BitrixAttachExistingBody,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        raise HTTPException(status_code=403, detail="portal_id mismatch")
    _require_portal_admin(db, portal_id, request)
    portal = db.get(Portal, portal_id)
    if not portal:
        raise HTTPException(status_code=404, detail="portal_not_found")
    _ensure_portal_can_attach(db, portal, int(body.account_id))

    user = _authenticate_web_user_for_bitrix(db, str(body.email), body.password)
    attachable = _build_bitrix_attachable_accounts(db, user)
    target = next((item for item in attachable if int(item.account_id) == int(body.account_id)), None)
    if not target:
        raise HTTPException(status_code=403, detail="forbidden")
    if not target.can_manage_integrations:
        raise HTTPException(status_code=403, detail="insufficient_role")
    if not target.attach_allowed:
        raise HTTPException(status_code=403, detail=target.reason or "bitrix_portal_limit_reached")

    portal.account_id = int(body.account_id)
    db.add(portal)
    _upsert_bitrix_account_integration(db, account_id=int(body.account_id), portal=portal)
    db.commit()
    return {
        "status": "linked",
        "action": "attach_existing",
        "account_id": int(body.account_id),
        "portal_id": int(portal_id),
    }


@router.post("/portals/{portal_id}/web/embedded-session")
async def create_embedded_session_for_linked_web_user(
    request: Request,
    portal_id: int,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        raise HTTPException(status_code=403, detail="portal_id mismatch")
    _require_portal_admin(db, portal_id, request)
    portal = db.get(Portal, portal_id)
    user = _resolve_linked_web_user(db, portal)
    if not portal or not portal.account_id or not user:
        raise HTTPException(status_code=404, detail="web_link_not_found")
    app_user_id = _get_app_user_id_for_web_user(db, user)
    if not app_user_id:
        raise HTTPException(status_code=400, detail="app_user_not_found")
    membership_ctx = _portal_account_membership_ctx(db, portal_id, user)
    if not membership_ctx:
        raise HTTPException(status_code=403, detail="portal_mismatch")
    session_token = _create_embedded_web_session(
        db,
        web_user=user,
        app_user_id=int(app_user_id),
        active_account_id=int(portal.account_id),
    )
    portal_token = create_portal_token_with_user(int(portal_id), int(portal.admin_user_id) if portal.admin_user_id else None, expires_minutes=60)
    account = db.get(Account, int(portal.account_id))
    return {
        "status": "ok",
        "session_token": session_token,
        "portal_id": int(portal_id),
        "portal_token": portal_token,
        "email": user.email,
        "active_account_id": int(portal.account_id),
        "accounts": _list_active_accounts(db, int(app_user_id)),
        "account_name": account.name if account else None,
        "account_no": int(account.account_no) if account and account.account_no is not None else None,
    }


@router.post("/portals/{portal_id}/web/login")
async def login_web_from_bitrix(
    request: Request,
    portal_id: int,
    body: WebLoginBody,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        raise HTTPException(status_code=403, detail="portal_id mismatch")
    _require_portal_admin(db, portal_id, request)
    email = body.email.lower().strip()
    user = _authenticate_web_user_for_bitrix(db, email, body.password)
    membership_ctx = _portal_account_membership_ctx(db, portal_id, user)
    if membership_ctx:
        demo_until = (user.created_at + timedelta(days=7)).date().isoformat()
        return {"status": "linked", "email": user.email, "demo_until": demo_until}
    if user.portal_id and int(user.portal_id) == int(portal_id):
        demo_until = (user.created_at + timedelta(days=7)).date().isoformat()
        return {"status": "linked", "email": user.email, "demo_until": demo_until}
    attachable_accounts = _build_bitrix_attachable_accounts(db, user)
    recommended_action = "create_account"
    if any(item.attach_allowed for item in attachable_accounts):
        recommended_action = "attach_existing"
    elif attachable_accounts:
        recommended_action = "upgrade_or_create"
    return {
        "status": "link_required",
        "email": user.email,
        "portal_id": int(portal_id),
        "recommended_action": recommended_action,
        "can_create_new_account": True,
        "attachable_accounts": [item.model_dump() for item in attachable_accounts],
    }


def _telegram_webhook_url(kind: str, portal_id: int, secret: str) -> str | None:
    s = get_settings()
    base = (s.public_base_url or "").rstrip("/")
    if not base:
        return None
    return f"{base}/v1/telegram/{kind}/{portal_id}/{secret}"


@router.get("/portals/{portal_id}/access/users")
async def get_portal_access_users(
    portal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    """Список разрешённых user_id портала."""
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
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
    return JSONResponse({"user_ids": user_ids, "items": items})


@router.get("/portals/{portal_id}/kb/files")
async def get_portal_kb_files(
    portal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    portal = db.get(Portal, int(portal_id))
    q = select(KBFile, KBSource.source_type, KBSource.url).join(KBSource, KBSource.id == KBFile.source_id, isouter=True)
    if portal and portal.account_id:
        q = q.where(
            sa.or_(
                KBFile.account_id == int(portal.account_id),
                sa.and_(KBFile.account_id.is_(None), KBFile.portal_id.in_(_account_scope_portal_ids(db, portal_id))),
            )
        )
    else:
        q = q.where(KBFile.portal_id.in_(_account_scope_portal_ids(db, portal_id)))
    q = q.order_by(KBFile.id.desc()).limit(200)
    rows = db.execute(q).all()
    # show only the latest entry per filename to hide stale errors
    seen: set[str] = set()
    items = []
    for f, source_type, source_url in rows:
        if not _acl_guard_file(db, file_rec=f, portal_id=portal_id, request=request):
            continue
        key = (f.filename or f.storage_path or str(f.id)).lower()
        if key in seen:
            continue
        seen.add(key)
        badges = _kb_file_access_badges(db, f)
        items.append({
            "id": f.id,
            "filename": f.filename,
            "folder_id": f.folder_id,
            "mime_type": f.mime_type,
            "source_type": source_type,
            "source_url": source_url,
            "size_bytes": f.size_bytes,
            "audience": f.audience or "staff",
            "status": f.status,
            "error_message": f.error_message,
            "uploaded_by_type": f.uploaded_by_type,
            "uploaded_by_id": f.uploaded_by_id,
            "uploaded_by_name": f.uploaded_by_name,
            "query_count": int(f.query_count or 0),
            "transcript_status": f.transcript_status,
            "transcript_error": f.transcript_error,
            "access_badges": badges,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        })
    return JSONResponse({"items": items})


@router.get("/portals/{portal_id}/kb/access-summary")
async def get_portal_kb_access_summary(
    portal_id: int,
    request: Request,
    folder_id: int | None = None,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    if folder_id is not None:
        rec = _account_scoped_kb_folder(db, portal_id, int(folder_id))
        if not rec:
            return _err(request, "not_found", "Folder not found", 404)
    return JSONResponse(_kb_client_access_summary(db, portal_id, folder_id=folder_id))


@router.get("/portals/{portal_id}/kb/search")
async def search_portal_kb(
    portal_id: int,
    q: str,
    request: Request,
    limit: int = 50,
    audience: str | None = None,
    file_ids: str | None = None,
    collection_ids: str | None = None,
    smart_folder_ids: str | None = None,
    topic_ids: str | None = None,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    if not q:
        if is_schema_v2(request):
            return JSONResponse({
                "ok": True,
                "data": {"file_ids": [], "matches": []},
                "meta": {"schema": "v2"},
            })
        return JSONResponse({"file_ids": [], "matches": []})
    aud = (audience or "staff").strip().lower()
    if aud not in ("staff", "client"):
        aud = "staff"
    acl_ctx = _portal_acl_subject_ctx(db, portal_id=portal_id, request=request, audience=aud)
    account_scope_ids = _all_account_scope_file_ids(db, portal_id=portal_id, audience=aud)
    account_scope_ids = _filter_file_ids_by_kb_acl(
        db,
        file_ids=account_scope_ids,
        membership_id=acl_ctx.get("membership_id"),
        group_ids=acl_ctx.get("group_ids"),
        role=acl_ctx.get("role"),
        audience=acl_ctx.get("audience"),
    )
    scoped_ids = _resolve_scope_file_ids(
        db,
        portal_id=portal_id,
        audience=aud,
        file_ids=_parse_csv_ints(file_ids),
        collection_ids=_parse_csv_ints(collection_ids),
        smart_folder_ids=_parse_csv_ints(smart_folder_ids),
        topic_ids=[x.strip() for x in str(topic_ids or "").split(",") if x.strip()],
    )
    if scoped_ids is None:
        scoped_ids = account_scope_ids
    else:
        scoped_ids &= account_scope_ids
    if scoped_ids is not None and not scoped_ids:
        if is_schema_v2(request):
            return JSONResponse({"ok": True, "data": {"file_ids": [], "matches": []}, "meta": {"schema": "v2", "audience": aud}})
        return JSONResponse({"file_ids": [], "matches": []})
    like_q = f"%{q}%"
    scope_portal_ids = _account_scope_portal_ids(db, portal_id)
    portal = db.get(Portal, int(portal_id))
    q_stmt = (
        select(
            KBFile.id,
            KBFile.filename,
            KBChunk.text,
            KBChunk.chunk_index,
            KBChunk.page_num,
            KBChunk.start_ms,
        )
        .join(KBChunk, KBChunk.file_id == KBFile.id)
        .where(
            KBFile.audience == aud,
            (KBChunk.text.ilike(like_q) | KBFile.filename.ilike(like_q)),
        )
        .order_by(KBFile.id.desc())
        .limit(max(1, min(limit, 200)))
    )
    if portal and portal.account_id:
        q_stmt = q_stmt.where(
            sa.or_(
                KBFile.account_id == int(portal.account_id),
                sa.and_(KBFile.account_id.is_(None), KBFile.portal_id.in_(scope_portal_ids)),
            )
        )
    else:
        q_stmt = q_stmt.where(KBFile.portal_id.in_(scope_portal_ids))
    if scoped_ids is not None:
        q_stmt = q_stmt.where(KBFile.id.in_(sorted(scoped_ids)))
    rows = db.execute(q_stmt).all()
    file_ids: list[int] = []
    matches = []
    seen: set[int] = set()
    for fid, fname, text, chunk_index, page_num, start_ms in rows:
        if fid in seen:
            continue
        seen.add(fid)
        file_ids.append(int(fid))
        snippet = (text or "").strip().replace("\n", " ")
        if len(snippet) > 160:
            snippet = snippet[:160] + "..."
        anchor_kind, anchor_value = _make_chunk_anchor(chunk_index, page_num, start_ms)
        matches.append(
            {
                "file_id": int(fid),
                "filename": fname,
                "snippet": snippet,
                "chunk_index": int(chunk_index) if chunk_index is not None else None,
                "page_num": int(page_num) if page_num is not None else None,
                "start_ms": int(start_ms) if start_ms is not None else None,
                "anchor_kind": anchor_kind,
                "anchor_value": anchor_value,
            }
        )
    if is_schema_v2(request):
        return JSONResponse({
            "ok": True,
            "data": {
                "file_ids": file_ids,
                "matches": matches,
            },
            "meta": {
                "schema": "v2",
                "audience": aud,
                "scope_file_ids": sorted(scoped_ids) if scoped_ids is not None else None,
            },
        })
    return JSONResponse({"file_ids": file_ids, "matches": matches})


@router.post("/portals/{portal_id}/kb/ask")
async def ask_portal_kb(
    portal_id: int,
    body: KBAskBody,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    query = (body.query or "").strip()
    if not query:
        return _err(request, "empty_query", "empty_query", 400)
    aud = (body.audience or "staff").strip().lower()
    if aud not in ("staff", "client"):
        aud = "staff"
    acl_ctx = _portal_acl_subject_ctx(db, portal_id=portal_id, request=request, audience=aud)
    account_scope_ids = _all_account_scope_file_ids(db, portal_id=portal_id, audience=aud)
    account_scope_ids = _filter_file_ids_by_kb_acl(
        db,
        file_ids=account_scope_ids,
        membership_id=acl_ctx.get("membership_id"),
        group_ids=acl_ctx.get("group_ids"),
        role=acl_ctx.get("role"),
        audience=acl_ctx.get("audience"),
    )
    scope = body.scope or {}
    scoped_ids = _resolve_scope_file_ids(
        db,
        portal_id=portal_id,
        audience=aud,
        file_ids=[int(x) for x in (scope.get("file_ids") or []) if str(x).isdigit()],
        collection_ids=[int(x) for x in (scope.get("collection_ids") or []) if str(x).isdigit()],
        smart_folder_ids=[int(x) for x in (scope.get("smart_folder_ids") or []) if str(x).isdigit()],
        topic_ids=[str(x).strip() for x in (scope.get("topic_ids") or []) if str(x).strip()],
    )
    if scoped_ids is None:
        scoped_ids = account_scope_ids
    else:
        scoped_ids &= account_scope_ids
    if scoped_ids is not None and not scoped_ids:
        if is_schema_v2(request):
            return JSONResponse({
                "ok": True,
                "data": {"answer": "В выбранной области поиска нет подходящих материалов.", "sources": [], "line_refs": {}},
                "meta": {"schema": "v2", "audience": aud, "scope_file_ids": []},
            })
        return JSONResponse({"answer": "В выбранной области поиска нет подходящих материалов."})
    overrides = {
        "show_sources": body.show_sources,
        "sources_format": body.sources_format,
    }
    answer, err, usage = answer_from_kb(
        db,
        portal_id,
        query,
        audience=aud,
        model_overrides=overrides,
        file_ids_filter=sorted(scoped_ids) if scoped_ids is not None else None,
    )
    if err:
        return _err(request, "kb_ask_failed", "kb_ask_failed", 400, detail=err)
    if is_schema_v2(request):
        sources = usage.get("sources") if isinstance(usage, dict) else []
        line_refs = usage.get("line_refs") if isinstance(usage, dict) else {}
        rag_debug = usage.get("rag_debug") if isinstance(usage, dict) else None
        _log_kb_ask_rag_debug(
            db=db,
            trace_id=_trace_id(request),
            portal_id=portal_id,
            path=f"/v1/bitrix/portals/{portal_id}/kb/ask",
            rag_debug=rag_debug if isinstance(rag_debug, dict) else None,
        )
        return JSONResponse({
            "ok": True,
            "data": {
                "answer": _strip_sources_block(answer),
                "sources": sources if isinstance(sources, list) else [],
                "line_refs": line_refs if isinstance(line_refs, dict) else {},
                "rag_debug": rag_debug if isinstance(rag_debug, dict) else None,
            },
            "meta": {
                "schema": "v2",
                "audience": aud,
                "scope_file_ids": sorted(scoped_ids) if scoped_ids is not None else None,
            },
        })
    return JSONResponse({"answer": answer})


@router.post("/portals/{portal_id}/kb/files/upload")
async def upload_portal_kb_file(
    portal_id: int,
    request: Request,
    file: UploadFile = File(...),
    audience: str | None = Form(default=None),
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не задан")
    owner_portal_id = _kb_storage_portal_id(db, portal_id)
    portal_dir = ensure_portal_dir(owner_portal_id)
    safe_name = os.path.basename(file.filename)
    suffix = uuid.uuid4().hex[:8]
    dst_path = os.path.join(portal_dir, f"{suffix}_{safe_name}")
    size, sha256 = save_upload(file.file, dst_path)
    uploader_type, uploader_id, uploader_name = _resolve_uploader(db, portal_id, request)
    aud = (audience or "staff").strip().lower()
    if aud not in ("staff", "client"):
        aud = "staff"
    is_media = _is_media_file(safe_name, file.content_type)
    media_enabled = is_media_transcription_enabled(db, portal_id)
    account_id = db.execute(select(Portal.account_id).where(Portal.id == portal_id)).scalar()
    if is_media and media_enabled and account_id:
        media_minutes = _estimate_media_minutes(dst_path)
        if would_exceed_account_media_minutes(db, int(account_id), additional_minutes=media_minutes):
            try:
                os.remove(dst_path)
            except Exception:
                pass
            return _err(request, "media_minutes_limit_reached", "media_minutes_limit_reached", 403)
    portal = db.get(Portal, int(portal_id))
    rec = KBFile(
        account_id=int(portal.account_id) if portal and portal.account_id else None,
        portal_id=owner_portal_id,
        filename=safe_name,
        audience=aud,
        mime_type=file.content_type,
        size_bytes=size,
        storage_path=dst_path,
        sha256=sha256,
        status="uploaded",
        uploaded_by_type=uploader_type,
        uploaded_by_id=uploader_id,
        uploaded_by_name=uploader_name,
        transcript_status=("queued" if (is_media and media_enabled) else ("not_enabled" if is_media else None)),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    job = KBJob(
        account_id=rec.account_id,
        portal_id=rec.portal_id,
        job_type="ingest",
        status="queued",
        payload_json={"file_id": rec.id},
    )
    db.add(job)
    rec.status = "queued"
    db.add(rec)
    db.commit()
    try:
        from redis import Redis
        from rq import Queue
        s = get_settings()
        r = Redis(host=s.redis_host, port=s.redis_port)
        q = Queue(s.rq_ingest_queue_name or "ingest", connection=r)
        q.enqueue(
            "apps.worker.jobs.process_kb_job",
            job.id,
            job_id=f"kbjob:{job.id}",
            job_timeout=max(300, int(s.kb_job_timeout_seconds or 3600)),
        )
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
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    portal = db.get(Portal, int(portal_id))
    scope_portal_ids = _account_scope_portal_ids(db, portal_id)
    if portal and portal.account_id:
        files = db.execute(
            select(KBFile).where(
                sa.or_(
                    KBFile.account_id == int(portal.account_id),
                    sa.and_(KBFile.account_id.is_(None), KBFile.portal_id.in_(scope_portal_ids)),
                ),
                KBFile.status.in_(["uploaded", "error", "queued"]),
            )
        ).scalars().all()
    else:
        files = db.execute(
            select(KBFile).where(
                KBFile.portal_id.in_(scope_portal_ids),
                KBFile.status.in_(["uploaded", "error", "queued"]),
            )
        ).scalars().all()
    if not files:
        return JSONResponse({"status": "ok", "queued": 0})
    account_id = db.execute(select(Portal.account_id).where(Portal.id == portal_id)).scalar()
    media_minutes_total = 0
    if account_id:
        for f in files:
            if _is_media_file(f.filename, f.mime_type) and is_media_transcription_enabled(db, portal_id):
                media_minutes_total += _estimate_media_minutes(f.storage_path or "")
        if media_minutes_total > 0 and would_exceed_account_media_minutes(db, int(account_id), additional_minutes=media_minutes_total):
            return _err(request, "media_minutes_limit_reached", "media_minutes_limit_reached", 403)
    queued = 0
    try:
        from redis import Redis
        from rq import Queue
        s = get_settings()
        r = Redis(host=s.redis_host, port=s.redis_port)
        q = Queue(s.rq_ingest_queue_name or "ingest", connection=r)
    except Exception:
        q = None
    for f in files:
        f.status = "queued"
        if _is_media_file(f.filename, f.mime_type):
            f.transcript_status = "queued" if is_media_transcription_enabled(db, portal_id) else "not_enabled"
            f.transcript_error = None
        job = KBJob(
            account_id=f.account_id,
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
                q.enqueue(
                    "apps.worker.jobs.process_kb_job",
                    job_id,
                    job_id=f"kbjob:{job_id}",
                    job_timeout=max(300, int(s.kb_job_timeout_seconds or 3600)),
                )
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
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    rec = _account_scoped_file(db, portal_id, file_id)
    if not rec:
        return _err(request, "not_found", "not_found", 404)
    account_id = db.execute(select(Portal.account_id).where(Portal.id == portal_id)).scalar()
    if account_id and _is_media_file(rec.filename, rec.mime_type) and is_media_transcription_enabled(db, portal_id):
        media_minutes = _estimate_media_minutes(rec.storage_path or "")
        if would_exceed_account_media_minutes(db, int(account_id), additional_minutes=media_minutes):
            return _err(request, "media_minutes_limit_reached", "media_minutes_limit_reached", 403)
    rec.status = "queued"
    rec.error_message = None
    if _is_media_file(rec.filename, rec.mime_type):
        rec.transcript_status = "queued" if is_media_transcription_enabled(db, portal_id) else "not_enabled"
        rec.transcript_error = None
    db.add(rec)
    job = KBJob(
        account_id=rec.account_id,
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
        q = Queue(s.rq_ingest_queue_name or "ingest", connection=r)
        q.enqueue(
            "apps.worker.jobs.process_kb_job",
            job.id,
            job_id=f"kbjob:{job.id}",
            job_timeout=max(300, int(s.kb_job_timeout_seconds or 3600)),
        )
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
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    rec = _account_scoped_file(db, portal_id, file_id)
    if not rec:
        return _err(request, "not_found", "not_found", 404)
    chunk_ids = db.execute(
        select(KBChunk.id).where(KBChunk.file_id == rec.id)
    ).scalars().all()
    # unlink from collections first (FK safety)
    db.execute(delete(KBCollectionFile).where(KBCollectionFile.file_id == rec.id))
    # drop pending/history jobs for this file
    if rec.account_id:
        jobs = db.execute(
            select(KBJob).where(KBJob.account_id == rec.account_id)
        ).scalars().all()
    else:
        jobs = db.execute(
            select(KBJob).where(KBJob.portal_id == rec.portal_id)
        ).scalars().all()
    job_ids_to_delete: list[int] = []
    for j in jobs:
        payload = j.payload_json if isinstance(j.payload_json, dict) else {}
        try:
            if int(payload.get("file_id") or 0) == int(rec.id):
                job_ids_to_delete.append(int(j.id))
        except Exception:
            continue
    if job_ids_to_delete:
        db.execute(delete(KBJob).where(KBJob.id.in_(job_ids_to_delete)))
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


@router.get("/portals/{portal_id}/kb/files/{file_id}/download")
async def download_kb_file(
    portal_id: int,
    file_id: int,
    request: Request,
    inline: int = 1,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    rec = _account_scoped_file(db, portal_id, file_id)
    rec = _acl_guard_file(db, file_rec=rec, portal_id=portal_id, request=request)
    if not rec:
        return _err(request, "not_found", "not_found", 404)
    if not rec.storage_path or not os.path.exists(rec.storage_path):
        return _err(request, "file_missing", "file_missing", 404)
    is_inline = int(inline or 0) == 1
    filename = rec.filename or os.path.basename(rec.storage_path)
    return FileResponse(
        rec.storage_path,
        media_type=rec.mime_type or "application/octet-stream",
        filename=filename,
        headers={"Content-Disposition": _content_disposition(filename, is_inline)},
    )


@router.get("/portals/{portal_id}/kb/files/{file_id}/signed-url")
async def get_kb_file_signed_url(
    portal_id: int,
    file_id: int,
    request: Request,
    inline: int = 1,
    ttl_seconds: int = 300,
    rendition: str | None = None,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    rec = _account_scoped_file(db, portal_id, file_id)
    rec = _acl_guard_file(db, file_rec=rec, portal_id=portal_id, request=request)
    if not rec:
        return _err(request, "not_found", "not_found", 404)
    ttl = max(30, min(int(ttl_seconds or 300), 3600))
    exp = int(time.time()) + ttl
    inl = 1 if int(inline or 0) == 1 else 0
    rend = (rendition or "original").strip().lower()
    if rend not in ("original", "preview_pdf"):
        rend = "original"
    if rend == "preview_pdf":
        candidate = f"{rec.storage_path}.preview.pdf" if rec.storage_path else ""
        if (not candidate or not os.path.exists(candidate)) and rec.storage_path and os.path.exists(rec.storage_path):
            # Best-effort on-demand rendition for already indexed files.
            try:
                from apps.backend.services.kb_ingest import _generate_preview_pdf  # type: ignore
                _generate_preview_pdf(rec.storage_path)
            except Exception:
                pass
        if not candidate or not os.path.exists(candidate):
            return _err(request, "preview_missing", "preview_missing", 404)
        _backfill_chunk_pages_from_preview(db, rec, candidate)
    sig = _make_file_sig(portal_id, file_id, exp, inl, rend)
    url = f"/api/v1/bitrix/portals/{portal_id}/kb/files/{file_id}/content?exp={exp}&inline={inl}&rendition={rend}&sig={sig}"
    return JSONResponse({"url": url, "expires_at": exp})


@router.get("/portals/{portal_id}/kb/files/{file_id}/content")
async def get_kb_file_content(
    portal_id: int,
    file_id: int,
    request: Request,
    exp: int,
    sig: str,
    inline: int = 1,
    rendition: str | None = None,
    db: Session = Depends(get_db),
):
    now = int(time.time())
    inl = 1 if int(inline or 0) == 1 else 0
    rend = (rendition or "original").strip().lower()
    if rend not in ("original", "preview_pdf"):
        rend = "original"
    expected = _make_file_sig(portal_id, file_id, int(exp), inl, rend)
    if int(exp) < now or not hmac.compare_digest(expected, str(sig or "")):
        return _err(request, "forbidden", "Forbidden", 403)
    rec = _account_scoped_file(db, portal_id, file_id)
    rec = _acl_guard_file(db, file_rec=rec, portal_id=portal_id, request=request)
    if not rec:
        return _err(request, "not_found", "not_found", 404)
    storage_path = rec.storage_path
    filename = rec.filename or (os.path.basename(rec.storage_path) if rec.storage_path else "file")
    media_type = rec.mime_type or "application/octet-stream"
    if rend == "preview_pdf":
        candidate = f"{rec.storage_path}.preview.pdf" if rec.storage_path else ""
        if (not candidate or not os.path.exists(candidate)) and rec.storage_path and os.path.exists(rec.storage_path):
            # Best-effort on-demand rendition for already indexed files.
            try:
                from apps.backend.services.kb_ingest import _generate_preview_pdf  # type: ignore
                _generate_preview_pdf(rec.storage_path)
            except Exception:
                pass
        if not candidate or not os.path.exists(candidate):
            return _err(request, "preview_missing", "preview_missing", 404)
        _backfill_chunk_pages_from_preview(db, rec, candidate)
        storage_path = candidate
        stem = os.path.splitext(filename or "file")[0]
        filename = f"{stem}.preview.pdf"
        media_type = "application/pdf"
    if not storage_path or not os.path.exists(storage_path):
        return _err(request, "file_missing", "file_missing", 404)
    return FileResponse(
        storage_path,
        media_type=media_type,
        filename=filename,
        headers={
            "Content-Disposition": _content_disposition(filename, inl == 1),
            "Accept-Ranges": "bytes",
            "Cache-Control": "private, max-age=60",
        },
    )


@router.get("/portals/{portal_id}/kb/files/{file_id}/chunks")
async def get_kb_file_chunks(
    portal_id: int,
    file_id: int,
    request: Request,
    limit: int = 1500,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    rec = _account_scoped_file(db, portal_id, file_id)
    rec = _acl_guard_file(db, file_rec=rec, portal_id=portal_id, request=request)
    if not rec:
        return _err(request, "not_found", "not_found", 404)
    lim = max(1, min(int(limit or 1500), 4000))
    rows = db.execute(
        select(KBChunk)
        .where(KBChunk.file_id == file_id)
        .order_by(KBChunk.chunk_index.asc())
        .limit(lim)
    ).scalars().all()
    items = []
    for r in rows:
        anchor_kind, anchor_value = _make_chunk_anchor(r.chunk_index, r.page_num, r.start_ms)
        items.append(
            {
                "id": r.id,
                "chunk_index": r.chunk_index,
                "text": r.text or "",
                "start_ms": r.start_ms,
                "end_ms": r.end_ms,
                "page_num": r.page_num,
                "anchor_kind": anchor_kind,
                "anchor_value": anchor_value,
            }
        )
    return JSONResponse({"items": items})


@router.get("/portals/{portal_id}/kb/files/{file_id}/transcript/status")
async def get_kb_file_transcript_status(
    portal_id: int,
    file_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    rec = _account_scoped_file(db, portal_id, file_id)
    rec = _acl_guard_file(db, file_rec=rec, portal_id=portal_id, request=request)
    if not rec:
        return _err(request, "not_found", "not_found", 404)
    is_media = _is_media_file(rec.filename, rec.mime_type)
    enabled = is_media_transcription_enabled(db, portal_id)
    status = (rec.transcript_status or "").strip().lower()
    if not status:
        if not is_media:
            status = "n/a"
        elif not enabled:
            status = "not_enabled"
        elif rec.status in ("queued", "processing"):
            status = "processing"
        elif rec.status == "ready":
            status = "ready"
        elif rec.status == "error":
            status = "error"
        else:
            status = "queued"
    return JSONResponse(
        {
            "allowed": bool(enabled),
            "is_media": bool(is_media),
            "status": status,
            "error": rec.transcript_error or rec.error_message,
        }
    )


@router.post("/portals/{portal_id}/kb/files/{file_id}/transcript/start")
async def start_kb_file_transcript(
    portal_id: int,
    file_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    rec = _account_scoped_file(db, portal_id, file_id)
    if not rec:
        return _err(request, "not_found", "not_found", 404)
    if not _is_media_file(rec.filename, rec.mime_type):
        return _err(request, "not_media_file", "not_media_file", 400)
    if not is_media_transcription_enabled(db, portal_id):
        return _err(request, "feature_not_enabled", "feature_not_enabled", 403)
    account_id = db.execute(select(Portal.account_id).where(Portal.id == portal_id)).scalar()
    if account_id:
        media_minutes = _estimate_media_minutes(rec.storage_path or "")
        if would_exceed_account_media_minutes(db, int(account_id), additional_minutes=media_minutes):
            return _err(request, "media_minutes_limit_reached", "media_minutes_limit_reached", 403)
    rec.status = "queued"
    rec.error_message = None
    rec.transcript_status = "queued"
    rec.transcript_error = None
    db.add(rec)
    job = KBJob(
        account_id=rec.account_id,
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
        q = Queue(s.rq_ingest_queue_name or "ingest", connection=r)
        q.enqueue(
            "apps.worker.jobs.process_kb_job",
            job.id,
            job_id=f"kbjob:{job.id}",
            job_timeout=max(300, int(s.kb_job_timeout_seconds or 3600)),
        )
    except Exception:
        pass
    return JSONResponse({"status": "ok", "job_id": job.id})


@router.get("/portals/{portal_id}/kb/files/{file_id}/transcript")
async def get_kb_file_transcript(
    portal_id: int,
    file_id: int,
    request: Request,
    limit: int = 2000,
    mode: str = "merged",
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    rec = _account_scoped_file(db, portal_id, file_id)
    rec = _acl_guard_file(db, file_rec=rec, portal_id=portal_id, request=request)
    if not rec:
        return _err(request, "not_found", "not_found", 404)
    if not _is_media_file(rec.filename, rec.mime_type):
        return _err(request, "not_media_file", "not_media_file", 400)
    if not is_media_transcription_enabled(db, portal_id):
        return _err(request, "feature_not_enabled", "feature_not_enabled", 403)
    lim = max(1, min(int(limit or 2000), 5000))
    # Preferred source for transcript panel: raw transcript segments from ingest file.
    # This avoids showing RAG chunks as if they were transcript turns.
    transcript_jsonl_path = (rec.storage_path or "") + ".transcript.jsonl"
    items = []
    if transcript_jsonl_path and os.path.exists(transcript_jsonl_path):
        try:
            with open(transcript_jsonl_path, "r", encoding="utf-8", errors="ignore") as f:
                for idx, line in enumerate(f):
                    if idx >= lim:
                        break
                    line = (line or "").strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except Exception:
                        continue
                    text = str(row.get("text") or "").strip()
                    if not text:
                        continue
                    items.append(
                        {
                            "id": -1 - idx,  # synthetic id for transcript rows
                            "chunk_index": idx,
                            "speaker": (str(row.get("speaker") or "").strip() or "Спикер A"),
                            "text": text,
                            "start_ms": int(row.get("start_ms") or 0),
                            "end_ms": int(row.get("end_ms") or 0),
                        }
                    )
        except Exception:
            items = []

    raw_items = items
    is_raw_mode = (mode or "merged").strip().lower() == "raw"
    if not is_raw_mode:
        items = merge_transcript_items(items)

    status = (rec.transcript_status or "").strip().lower() or "ready"
    if not items and status == "ready":
        status = "missing"

    merged_count = len(merge_transcript_items(raw_items)) if raw_items else 0
    return JSONResponse(
        {
            "items": items,
            "status": status,
            "mode": "raw" if is_raw_mode else "merged",
            "raw_count": len(raw_items),
            "merged_count": merged_count,
        }
    )


@router.get("/portals/{portal_id}/kb/collections")
async def list_kb_collections(
    portal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    portal = db.get(Portal, int(portal_id))
    if portal and portal.account_id:
        rows = db.execute(
            select(KBCollection)
            .where(
                sa.or_(
                    KBCollection.account_id == int(portal.account_id),
                    sa.and_(KBCollection.account_id.is_(None), KBCollection.portal_id.in_(_account_scope_portal_ids(db, portal_id))),
                )
            )
            .order_by(KBCollection.id.desc())
        ).scalars().all()
    else:
        scope_portal_ids = _account_scope_portal_ids(db, portal_id)
        rows = db.execute(
            select(KBCollection).where(KBCollection.portal_id.in_(scope_portal_ids)).order_by(KBCollection.id.desc())
        ).scalars().all()
    if rows:
        counts = dict(db.execute(
            select(KBCollectionFile.collection_id, func.count())
            .where(KBCollectionFile.collection_id.in_([r.id for r in rows]))
            .group_by(KBCollectionFile.collection_id)
        ).all())
    else:
        counts = {}
    return JSONResponse({
        "items": [
            {
                "id": c.id,
                "name": c.name,
                "color": c.color,
                "file_count": int(counts.get(c.id) or 0),
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in rows
        ]
    })


@router.post("/portals/{portal_id}/kb/collections")
async def create_kb_collection(
    portal_id: int,
    request: Request,
    body: CollectionBody,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    name = (body.name or "").strip()
    if not name:
        return _err(request, "missing_name", "missing_name", 400)
    portal = db.get(Portal, int(portal_id))
    owner_portal_id = _kb_storage_portal_id(db, portal_id)
    rec = KBCollection(
        account_id=int(portal.account_id) if portal and portal.account_id else None,
        portal_id=owner_portal_id,
        name=name[:128],
        color=(body.color or "").strip() or None,
        created_at=datetime.utcnow(),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return JSONResponse({"id": rec.id, "name": rec.name, "color": rec.color})


@router.patch("/portals/{portal_id}/kb/collections/{collection_id}")
async def update_kb_collection(
    portal_id: int,
    collection_id: int,
    request: Request,
    body: CollectionBody,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    rec = _account_scoped_collection(db, portal_id, collection_id)
    if not rec:
        return _err(request, "not_found", "not_found", 404)
    if body.name is not None:
        name = (body.name or "").strip()
        if name:
            rec.name = name[:128]
    if body.color is not None:
        rec.color = (body.color or "").strip() or None
    db.add(rec)
    db.commit()
    return JSONResponse({"status": "ok"})


@router.delete("/portals/{portal_id}/kb/collections/{collection_id}")
async def delete_kb_collection(
    portal_id: int,
    collection_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    rec = _account_scoped_collection(db, portal_id, collection_id)
    if not rec:
        return _err(request, "not_found", "not_found", 404)
    db.execute(delete(KBCollectionFile).where(KBCollectionFile.collection_id == collection_id))
    db.execute(delete(KBCollection).where(KBCollection.id == collection_id))
    db.commit()
    return JSONResponse({"status": "ok"})


@router.post("/portals/{portal_id}/kb/collections/{collection_id}/files")
async def add_file_to_collection(
    portal_id: int,
    collection_id: int,
    request: Request,
    body: CollectionFileBody,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    rec = _account_scoped_collection(db, portal_id, collection_id)
    if not rec:
        return _err(request, "collection_not_found", "collection_not_found", 404)
    file_rec = _account_scoped_file(db, portal_id, body.file_id)
    if not file_rec:
        return _err(request, "file_not_found", "file_not_found", 404)
    settings = get_portal_kb_settings(db, portal_id)
    multi = bool(settings.get("collections_multi_assign")) if settings.get("collections_multi_assign") is not None else True
    if not multi:
        db.execute(delete(KBCollectionFile).where(KBCollectionFile.file_id == file_rec.id))
    exists = db.execute(
        select(KBCollectionFile).where(
            KBCollectionFile.collection_id == collection_id,
            KBCollectionFile.file_id == file_rec.id,
        )
    ).scalar_one_or_none()
    if not exists:
        db.add(KBCollectionFile(collection_id=collection_id, file_id=file_rec.id, created_at=datetime.utcnow()))
        db.commit()
    return JSONResponse({"status": "ok"})


@router.get("/portals/{portal_id}/kb/collections/{collection_id}/files")
async def list_collection_files(
    portal_id: int,
    collection_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    collection = _account_scoped_collection(db, portal_id, collection_id)
    if not collection:
        return _err(request, "not_found", "not_found", 404)
    rows = [
        int(x)
        for x in db.execute(
        select(KBCollectionFile.file_id)
        .where(KBCollectionFile.collection_id == collection_id)
        ).scalars().all()
    ]
    acl_ctx = _portal_acl_subject_ctx(db, portal_id=portal_id, request=request, audience="staff")
    allowed_ids = _filter_file_ids_by_kb_acl(
        db,
        file_ids=set(rows),
        membership_id=acl_ctx.get("membership_id"),
        group_ids=acl_ctx.get("group_ids"),
        role=acl_ctx.get("role"),
        audience=acl_ctx.get("audience"),
    )
    return JSONResponse({"file_ids": [int(x) for x in rows if int(x) in allowed_ids]})


@router.delete("/portals/{portal_id}/kb/collections/{collection_id}/files/{file_id}")
async def remove_file_from_collection(
    portal_id: int,
    collection_id: int,
    file_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    collection = _account_scoped_collection(db, portal_id, collection_id)
    if not collection:
        return _err(request, "collection_not_found", "collection_not_found", 404)
    file_rec = _account_scoped_file(db, portal_id, file_id)
    if not file_rec:
        return _err(request, "file_not_found", "file_not_found", 404)
    db.execute(
        delete(KBCollectionFile).where(
            KBCollectionFile.collection_id == collection_id,
            KBCollectionFile.file_id == file_rec.id,
        )
    )
    db.commit()
    return JSONResponse({"status": "ok"})


@router.get("/portals/{portal_id}/kb/smart-folders")
async def list_kb_smart_folders(
    portal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    portal = db.get(Portal, int(portal_id))
    if portal and portal.account_id:
        rows = db.execute(
            select(KBSmartFolder)
            .where(
                sa.or_(
                    KBSmartFolder.account_id == int(portal.account_id),
                    sa.and_(KBSmartFolder.account_id.is_(None), KBSmartFolder.portal_id.in_(_account_scope_portal_ids(db, portal_id))),
                )
            )
            .order_by(KBSmartFolder.id.desc())
        ).scalars().all()
    else:
        scope_portal_ids = _account_scope_portal_ids(db, portal_id)
        rows = db.execute(
            select(KBSmartFolder).where(KBSmartFolder.portal_id.in_(scope_portal_ids)).order_by(KBSmartFolder.id.desc())
        ).scalars().all()
    return JSONResponse({
        "items": [
            {
                "id": r.id,
                "name": r.name,
                "system_tag": r.system_tag,
                "rules": r.rules_json or {},
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    })


@router.post("/portals/{portal_id}/kb/smart-folders")
async def create_kb_smart_folder(
    portal_id: int,
    request: Request,
    body: SmartFolderBody,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    name = (body.name or "").strip()
    if not name:
        return _err(request, "missing_name", "missing_name", 400)
    portal = db.get(Portal, int(portal_id))
    owner_portal_id = _kb_storage_portal_id(db, portal_id)
    rec = KBSmartFolder(
        account_id=int(portal.account_id) if portal and portal.account_id else None,
        portal_id=owner_portal_id,
        name=name[:128],
        system_tag=(body.system_tag or "").strip() or None,
        rules_json=body.rules_json or {},
        created_at=datetime.utcnow(),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return JSONResponse({"id": rec.id, "name": rec.name})


@router.get("/portals/{portal_id}/kb/folders")
async def list_kb_folders(
    portal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    _ensure_kb_root_folders(db, portal_id)
    portal = db.get(Portal, int(portal_id))
    scope_portal_ids = _account_scope_portal_ids(db, portal_id)
    if portal and portal.account_id:
        rows = db.execute(
            select(KBFolder)
            .where(
                sa.or_(
                    KBFolder.account_id == int(portal.account_id),
                    sa.and_(KBFolder.account_id.is_(None), KBFolder.portal_id.in_(scope_portal_ids)),
                )
            )
            .order_by(KBFolder.parent_id.asc().nullsfirst(), KBFolder.id.asc())
        ).scalars().all()
    else:
        rows = db.execute(
            select(KBFolder).where(KBFolder.portal_id.in_(scope_portal_ids)).order_by(KBFolder.parent_id.asc().nullsfirst(), KBFolder.id.asc())
        ).scalars().all()
    folder_map = {int(row.id): row for row in rows}
    return JSONResponse(
        {
            "items": [
                {
                    "id": row.id,
                    "name": row.name,
                    "parent_id": row.parent_id,
                    "root_space": _kb_folder_root_space(row, folder_map),
                    "is_space_root": bool(str(row.root_space or "").strip().lower() in KB_ROOT_SPACE_LABELS),
                    "access_badges": _kb_folder_access_badges(db, int(row.id)),
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]
        }
    )


@router.post("/portals/{portal_id}/kb/folders")
async def create_kb_folder(
    portal_id: int,
    request: Request,
    body: FolderBody,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    _ensure_kb_root_folders(db, portal_id)
    name = (body.name or "").strip()
    if not name:
        return _err(request, "missing_name", "missing_name", 400)
    parent = None
    if body.parent_id:
        parent = _account_scoped_kb_folder(db, portal_id, int(body.parent_id))
        if not parent:
            return _err(request, "parent_not_found", "parent_not_found", 404)
    portal = db.get(Portal, int(portal_id))
    owner_portal_id = _kb_storage_portal_id(db, portal_id)
    rec = KBFolder(
        account_id=int(portal.account_id) if portal and portal.account_id else None,
        portal_id=owner_portal_id,
        parent_id=parent.id if parent else None,
        root_space=None,
        name=name[:128],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    root_space = _kb_folder_root_space(rec, {int(rec.id): rec, **({int(parent.id): parent} if parent else {})})
    return JSONResponse({"id": rec.id, "name": rec.name, "parent_id": rec.parent_id, "root_space": root_space, "is_space_root": False})


@router.patch("/portals/{portal_id}/kb/folders/{folder_id}")
async def update_kb_folder(
    portal_id: int,
    folder_id: int,
    request: Request,
    body: FolderBody,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    _ensure_kb_root_folders(db, portal_id)
    rec = _account_scoped_kb_folder(db, portal_id, folder_id)
    if not rec:
        return _err(request, "not_found", "not_found", 404)
    if str(rec.root_space or "").strip().lower() in KB_ROOT_SPACE_LABELS:
        if body.parent_id is not None:
            return _err(request, "space_root_locked", "space_root_locked", 409)
        name = (body.name or "").strip()
        if name and name[:128] != rec.name:
            return _err(request, "space_root_locked", "space_root_locked", 409)
        return JSONResponse({"status": "ok"})
    name = (body.name or "").strip()
    if name:
        rec.name = name[:128]
    if body.parent_id is not None:
        if int(body.parent_id or 0) == int(rec.id):
            return _err(request, "invalid_parent", "invalid_parent", 400)
        if body.parent_id:
            parent = _account_scoped_kb_folder(db, portal_id, int(body.parent_id))
            if not parent:
                return _err(request, "parent_not_found", "parent_not_found", 404)
            rec.parent_id = int(parent.id)
        else:
            rec.parent_id = None
    rec.updated_at = datetime.utcnow()
    db.add(rec)
    db.commit()
    return JSONResponse({"status": "ok"})


@router.delete("/portals/{portal_id}/kb/folders/{folder_id}")
async def delete_kb_folder(
    portal_id: int,
    folder_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    _ensure_kb_root_folders(db, portal_id)
    rec = _account_scoped_kb_folder(db, portal_id, folder_id)
    if not rec:
        return _err(request, "not_found", "not_found", 404)
    if str(rec.root_space or "").strip().lower() in KB_ROOT_SPACE_LABELS:
        return _err(request, "space_root_locked", "space_root_locked", 409)
    has_children = db.execute(select(KBFolder.id).where(KBFolder.parent_id == rec.id).limit(1)).scalar_one_or_none()
    has_files = db.execute(select(KBFile.id).where(KBFile.folder_id == rec.id).limit(1)).scalar_one_or_none()
    if has_children or has_files:
        return _err(request, "folder_not_empty", "folder_not_empty", 409)
    db.execute(delete(KBFolder).where(KBFolder.id == rec.id))
    db.commit()
    return JSONResponse({"status": "ok"})


@router.post("/portals/{portal_id}/kb/files/{file_id}/folder")
async def move_kb_file_to_folder(
    portal_id: int,
    file_id: int,
    request: Request,
    body: FileFolderBody,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    rec = _account_scoped_file(db, portal_id, file_id)
    if not rec:
        return _err(request, "file_not_found", "file_not_found", 404)
    folder = None
    if body.folder_id:
        folder = _account_scoped_kb_folder(db, portal_id, int(body.folder_id))
        if not folder:
            return _err(request, "folder_not_found", "folder_not_found", 404)
    rec.folder_id = int(folder.id) if folder else None
    rec.updated_at = datetime.utcnow()
    db.add(rec)
    db.commit()
    return JSONResponse({"status": "ok", "folder_id": rec.folder_id})


@router.get("/portals/{portal_id}/kb/folders/{folder_id}/access")
async def get_kb_folder_access(
    portal_id: int,
    folder_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    rec = _account_scoped_kb_folder(db, portal_id, folder_id)
    if not rec:
        return _err(request, "not_found", "not_found", 404)
    rows = db.execute(
        select(KBFolderAccess)
        .where(KBFolderAccess.folder_id == rec.id)
        .order_by(KBFolderAccess.id.asc())
    ).scalars().all()
    return JSONResponse({"items": _acl_items_payload(rows)})


@router.put("/portals/{portal_id}/kb/folders/{folder_id}/access")
async def put_kb_folder_access(
    portal_id: int,
    folder_id: int,
    request: Request,
    body: ACLListBody,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    rec = _account_scoped_kb_folder(db, portal_id, folder_id)
    if not rec:
        return _err(request, "not_found", "not_found", 404)
    try:
        items = _replace_folder_acl(db, rec.id, body.items or [])
    except ValueError as exc:
        return _err(request, str(exc), str(exc), 400)
    db.commit()
    return JSONResponse({"status": "ok", "items": items})


@router.get("/portals/{portal_id}/kb/files/{file_id}/access")
async def get_kb_file_access(
    portal_id: int,
    file_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    _ensure_kb_root_folders(db, portal_id)
    rec = _account_scoped_file(db, portal_id, file_id)
    if not rec:
        return _err(request, "not_found", "not_found", 404)
    rows = db.execute(
        select(KBFileAccess)
        .where(KBFileAccess.file_id == rec.id)
        .order_by(KBFileAccess.id.asc())
    ).scalars().all()
    return JSONResponse({"items": _acl_items_payload(rows)})


@router.put("/portals/{portal_id}/kb/files/{file_id}/access")
async def put_kb_file_access(
    portal_id: int,
    file_id: int,
    request: Request,
    body: ACLListBody,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    rec = _account_scoped_file(db, portal_id, file_id)
    if not rec:
        return _err(request, "not_found", "not_found", 404)
    try:
        items = _replace_file_acl(db, rec.id, body.items or [])
    except ValueError as exc:
        return _err(request, str(exc), str(exc), 400)
    db.commit()
    return JSONResponse({"status": "ok", "items": items})


@router.get("/portals/{portal_id}/kb/files/{file_id}/access/effective")
async def get_kb_file_effective_access_preview(
    portal_id: int,
    file_id: int,
    request: Request,
    membership_id: int | None = None,
    role: str | None = None,
    audience: str | None = None,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    rec = _account_scoped_file(db, portal_id, file_id)
    if not rec:
        return _err(request, "not_found", "not_found", 404)
    group_ids = _kb_group_ids_for_membership(db, membership_id)
    folder_access = "none"
    if rec.folder_id:
        folder_rows = db.execute(
            select(KBFolderAccess.principal_type, KBFolderAccess.principal_id, KBFolderAccess.access_level)
            .where(KBFolderAccess.folder_id == rec.folder_id)
        ).all()
        folder_access = resolve_kb_acl_access(
            [(r[0], r[1], r[2]) for r in folder_rows],
            kb_acl_principals_for_membership(membership_id, role, audience, group_ids),
        )
    file_rows = db.execute(
        select(KBFileAccess.principal_type, KBFileAccess.principal_id, KBFileAccess.access_level)
        .where(KBFileAccess.file_id == rec.id)
    ).all()
    effective = resolve_kb_acl_access(
        [(r[0], r[1], r[2]) for r in file_rows],
        kb_acl_principals_for_membership(membership_id, role, audience, group_ids),
        inherited_access=folder_access,
    )
    return JSONResponse({"folder_access": folder_access, "effective_access": effective})


@router.delete("/portals/{portal_id}/kb/smart-folders/{folder_id}")
async def delete_kb_smart_folder(
    portal_id: int,
    folder_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    rec = _account_scoped_smart_folder(db, portal_id, folder_id)
    if not rec:
        return _err(request, "not_found", "not_found", 404)
    db.execute(delete(KBSmartFolder).where(KBSmartFolder.id == folder_id))
    db.commit()
    return JSONResponse({"status": "ok"})


@router.get("/portals/{portal_id}/kb/topics")
async def get_kb_topics(
    portal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    acl_ctx = _portal_acl_subject_ctx(db, portal_id=portal_id, request=request, audience="staff")
    portal = db.get(Portal, int(portal_id))
    scope_portal_ids = _account_scope_portal_ids(db, portal_id)
    if portal and portal.account_id:
        files = db.execute(
            select(KBFile.id, KBFile.filename)
            .where(
                sa.or_(
                    KBFile.account_id == int(portal.account_id),
                    sa.and_(KBFile.account_id.is_(None), KBFile.portal_id.in_(scope_portal_ids)),
                )
            )
            .order_by(KBFile.id.desc())
        ).all()
    else:
        files = db.execute(
            select(KBFile.id, KBFile.filename)
            .where(KBFile.portal_id.in_(scope_portal_ids))
            .order_by(KBFile.id.desc())
        ).all()
    file_ids_allowed = _filter_file_ids_by_kb_acl(
        db,
        file_ids={int(file_id) for file_id, _filename in files},
        membership_id=acl_ctx.get("membership_id"),
        group_ids=acl_ctx.get("group_ids"),
        role=acl_ctx.get("role"),
        audience=acl_ctx.get("audience"),
    )
    files = [(file_id, filename) for file_id, filename in files if int(file_id) in file_ids_allowed]
    topic_hits: dict[str, list[int]] = {t["id"]: [] for t in _KB_TOPICS}
    file_texts: list[tuple[int, str]] = []
    for file_id, filename in files:
        chunks = db.execute(
            select(KBChunk.text)
            .where(KBChunk.file_id == file_id)
            .limit(20)
        ).scalars().all()
        text = (filename or "") + " " + " ".join(chunks)
        file_texts.append((int(file_id), text))
        for t in _KB_TOPICS:
            if _topic_matches(text, t["keywords"]):
                topic_hits[t["id"]].append(int(file_id))
    settings = get_portal_kb_settings(db, portal_id)
    threshold = int(settings.get("smart_folder_threshold") or 5)
    if portal and portal.account_id:
        existing = db.execute(
            select(KBSmartFolder.system_tag)
            .where(
                sa.or_(
                    KBSmartFolder.account_id == int(portal.account_id),
                    sa.and_(KBSmartFolder.account_id.is_(None), KBSmartFolder.portal_id.in_(scope_portal_ids)),
                ),
                KBSmartFolder.system_tag.isnot(None),
            )
        ).scalars().all()
        existing_names = db.execute(
            select(KBSmartFolder.name).where(
                sa.or_(
                    KBSmartFolder.account_id == int(portal.account_id),
                    sa.and_(KBSmartFolder.account_id.is_(None), KBSmartFolder.portal_id.in_(scope_portal_ids)),
                )
            )
        ).scalars().all()
    else:
        existing = db.execute(
            select(KBSmartFolder.system_tag)
            .where(KBSmartFolder.portal_id.in_(scope_portal_ids), KBSmartFolder.system_tag.isnot(None))
        ).scalars().all()
        existing_names = db.execute(
            select(KBSmartFolder.name).where(KBSmartFolder.portal_id.in_(scope_portal_ids))
        ).scalars().all()
    existing_tags = {str(x) for x in existing if x}
    existing_name_set = {str(x or "").strip().lower() for x in existing_names if str(x or "").strip()}
    topics_out = []
    suggestions = []
    min_count = max(1, threshold)
    for t in _KB_TOPICS:
        ids = topic_hits.get(t["id"], [])
        topics_out.append({
            "id": t["id"],
            "name": t["name"],
            "count": len(ids),
            "file_ids": ids,
        })
        if (
            len(ids) >= min_count
            and _is_two_part_topic_name(str(t["name"]))
            and t["id"] not in existing_tags
            and str(t["name"]).strip().lower() not in existing_name_set
        ):
            suggestions.append({"id": t["id"], "name": t["name"], "count": len(ids)})
    excluded = set()
    for t in _KB_TOPICS:
        for kw in t.get("keywords", []):
            for tok in re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]{4,}", str(kw).lower()):
                excluded.add(tok)
    auto_topics = _auto_topic_candidates(file_texts, threshold=threshold, excluded_tokens=excluded, limit=8)
    for at in auto_topics:
        topics_out.append(
            {
                "id": at["id"],
                "name": at["name"],
                "count": at["count"],
                "file_ids": at["file_ids"],
            }
        )
        if _is_two_part_topic_name(str(at["name"])) and at["name"].strip().lower() not in existing_name_set:
            suggestions.append({"id": at["id"], "name": at["name"], "count": at["count"], "auto": True})
    if not suggestions:
        fallback = sorted(
            [
                t for t in topics_out
                if int(t.get("count") or 0) >= min_count
                and _is_two_part_topic_name(str(t.get("name") or ""))
                and str(t.get("name") or "").strip().lower() not in existing_name_set
            ],
            key=lambda x: int(x.get("count") or 0),
            reverse=True,
        )[:8]
        suggestions = [
            {"id": str(t.get("id") or ""), "name": str(t.get("name") or ""), "count": int(t.get("count") or 0)}
            for t in fallback
        ]
    return JSONResponse({
        "threshold": threshold,
        "topics": topics_out,
        "suggestions": suggestions,
    })


@router.get("/portals/{portal_id}/kb/settings")
async def get_portal_kb_settings_api(
    portal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    out = get_portal_kb_settings(db, portal_id)
    out["settings_portal_id"] = int(out.get("settings_portal_id") or portal_id)
    out["settings_scope"] = str(out.get("settings_scope") or ("account" if out.get("settings_account_id") else "portal"))
    available, reason = _diarization_runtime_status()
    diar_gate = ((out.get("feature_gates") or {}).get("speaker_diarization") or {})
    media_gate = ((out.get("feature_gates") or {}).get("media_transcription") or {})
    out["model_selection_available"] = bool((((out.get("feature_gates") or {}).get("model_selection") or {}).get("allowed", True)))
    out["model_selection_reason"] = (((out.get("feature_gates") or {}).get("model_selection") or {}).get("reason") or "")
    out["advanced_tuning_available"] = bool((((out.get("feature_gates") or {}).get("advanced_model_tuning") or {}).get("allowed", True)))
    out["advanced_tuning_reason"] = (((out.get("feature_gates") or {}).get("advanced_model_tuning") or {}).get("reason") or "")
    out["media_transcription_available"] = bool(media_gate.get("allowed", True))
    out["media_transcription_reason"] = (media_gate.get("reason") or "")
    out["speaker_diarization_available"] = bool(diar_gate.get("allowed", True)) and available
    out["speaker_diarization_reason"] = (diar_gate.get("reason") or reason or "")
    return JSONResponse(out)


@router.get("/portals/{portal_id}/billing/policy")
async def get_portal_billing_policy_api(
    portal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    gates, policy, portal = _portal_product_gates(db, portal_id)
    account = db.get(Account, int(portal.account_id)) if portal and portal.account_id else None
    return JSONResponse({
        "account": {
            "id": int(account.id) if account else None,
            "name": account.name if account else None,
            "account_no": int(account.account_no) if account and account.account_no is not None else None,
            "slug": account.slug if account else None,
        },
        "billing_policy": {
            "plan_code": policy.get("plan_code") or "default",
            "plan_name": ((policy.get("plan") or {}).get("name") if isinstance(policy.get("plan"), dict) else None) or "Default",
            "source": policy.get("source") or "default",
            "features": dict(policy.get("features") or {}),
            "limits": dict(policy.get("limits") or {}),
        },
        "feature_gates": gates,
    })


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
    show_sources: bool | None = None
    sources_format: str | None = None
    media_transcription_enabled: bool | None = None
    speaker_diarization_enabled: bool | None = None
    collections_multi_assign: bool | None = None
    smart_folder_threshold: int | None = None


class PortalKBSourceBody(BaseModel):
    url: str
    title: str | None = None
    audience: str | None = None


@router.post("/portals/{portal_id}/kb/settings")
async def set_portal_kb_settings_api(
    portal_id: int,
    body: PortalKBSettingsBody,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    policy = get_portal_effective_policy(db, portal_id)
    features = dict(policy.get("features") or {})
    if not bool(features.get("allow_model_selection", True)):
        body.embedding_model = None
        body.chat_model = None
        body.api_base = None
    if not bool(features.get("allow_advanced_model_tuning", True)):
        body.temperature = None
        body.max_tokens = None
        body.top_p = None
        body.presence_penalty = None
        body.frequency_penalty = None
        body.context_messages = None
        body.context_chars = None
        body.retrieval_top_k = None
        body.retrieval_max_chars = None
        body.lex_boost = None
        body.system_prompt_extra = None
    if not bool(features.get("allow_media_transcription", True)):
        body.media_transcription_enabled = False
        body.speaker_diarization_enabled = False
    elif not bool(features.get("allow_speaker_diarization", True)):
        body.speaker_diarization_enabled = False
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
        show_sources=body.show_sources,
        sources_format=body.sources_format,
        media_transcription_enabled=body.media_transcription_enabled,
        speaker_diarization_enabled=body.speaker_diarization_enabled,
        collections_multi_assign=body.collections_multi_assign,
        smart_folder_threshold=body.smart_folder_threshold,
    )
    out["settings_portal_id"] = int(out.get("settings_portal_id") or portal_id)
    out["settings_scope"] = str(out.get("settings_scope") or ("account" if out.get("settings_account_id") else "portal"))
    return JSONResponse(out)


@router.get("/portals/{portal_id}/telegram/staff")
async def get_portal_telegram_staff_settings(
    portal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    settings = get_portal_telegram_settings(db, portal_id)
    secret = get_portal_telegram_secret(db, portal_id, "staff") or ""
    webhook_url = _telegram_webhook_url("staff", portal_id, secret) if secret else None
    return JSONResponse({"kind": "staff", **settings.get("staff", {}), "webhook_url": webhook_url})


@router.post("/portals/{portal_id}/telegram/staff")
async def set_portal_telegram_staff_settings(
    portal_id: int,
    body: TelegramBotSettingsBody,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
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
    return JSONResponse({
        "kind": "staff",
        **settings.get("staff", {}),
        "webhook_url": webhook_url,
        "webhook_ok": webhook_ok,
        "webhook_error": webhook_error,
        "bot_username": bot_info.get("username") if bot_info else None,
        "bot_id": bot_info.get("id") if bot_info else None,
    })


@router.get("/portals/{portal_id}/telegram/client")
async def get_portal_telegram_client_settings(
    portal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    gates, policy, _portal = _portal_product_gates(db, portal_id)
    settings = get_portal_telegram_settings(db, portal_id)
    secret = get_portal_telegram_secret(db, portal_id, "client") or ""
    webhook_url = _telegram_webhook_url("client", portal_id, secret) if secret else None
    return JSONResponse({
        "kind": "client",
        **settings.get("client", {}),
        "webhook_url": webhook_url,
        "client_bot_available": bool((gates.get("client_bot") or {}).get("allowed", True)),
        "client_bot_reason": (gates.get("client_bot") or {}).get("reason") or "",
        "billing_policy": {
            "plan_code": policy.get("plan_code") or "default",
            "plan_name": ((policy.get("plan") or {}).get("name") if isinstance(policy.get("plan"), dict) else None) or "Default",
        },
    })


@router.post("/portals/{portal_id}/telegram/client")
async def set_portal_telegram_client_settings(
    portal_id: int,
    body: TelegramBotSettingsBody,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    gates, _policy, _portal = _portal_product_gates(db, portal_id)
    if not bool((gates.get("client_bot") or {}).get("allowed", True)):
        return _err(request, "client_bot_locked", "client_bot_locked", 403, detail="Feature unavailable on current plan")
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
    return JSONResponse({
        "kind": "client",
        **settings.get("client", {}),
        "webhook_url": webhook_url,
        "webhook_ok": webhook_ok,
        "webhook_error": webhook_error,
        "bot_username": bot_info.get("username") if bot_info else None,
        "bot_id": bot_info.get("id") if bot_info else None,
    })


@router.post("/portals/{portal_id}/bitrix/credentials")
async def set_portal_bitrix_credentials(
    portal_id: int,
    body: LocalBitrixCredentialsBody,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    portal = _require_portal_admin(db, portal_id, request)
    client_id = (body.client_id or "").strip()
    client_secret = (body.client_secret or "").strip()
    if not client_id or not client_secret:
        return _err(request, "missing_credentials", "client_id/client_secret required", 400)
    s = get_settings()
    enc = s.token_encryption_key or s.secret_key
    portal.local_client_id = client_id
    portal.local_client_secret_encrypted = encrypt_token(client_secret, enc)
    db.add(portal)
    db.commit()
    masked = f"{client_id[:6]}...{client_id[-4:]}" if len(client_id) > 10 else f"{client_id[:2]}...{client_id[-2:]}"
    refreshed = False
    refresh_error = None
    try:
        refresh_portal_tokens(db, portal_id, trace_id=_trace_id(request))
        refreshed = True
    except BitrixAuthError as e:
        refresh_error = e.code
    return JSONResponse({"ok": True, "client_id_masked": masked, "refreshed": refreshed, "refresh_error": refresh_error})


@router.get("/portals/{portal_id}/bitrix/credentials")
async def get_portal_bitrix_credentials(
    portal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    portal = db.get(Portal, portal_id)
    if not portal:
        return _err(request, "portal_not_found", "portal_not_found", 404)
    client_id = portal.local_client_id or ""
    if not client_id:
        return JSONResponse({"ok": True, "client_id_masked": ""})
    masked = f"{client_id[:6]}...{client_id[-4:]}" if len(client_id) > 10 else f"{client_id[:2]}...{client_id[-2:]}"
    return JSONResponse({"ok": True, "client_id_masked": masked})


@router.get("/portals/{portal_id}/kb/models")
async def get_portal_kb_models(
    portal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    # use global token/settings
    from apps.backend.services.kb_settings import get_gigachat_settings, get_gigachat_access_token_plain, get_valid_gigachat_access_token
    settings = get_gigachat_settings(db)
    api_base = settings.get("api_base") or DEFAULT_API_BASE
    token, err = get_valid_gigachat_access_token(db)
    if err or not token:
        return _err(request, err or "missing_access_token", err or "missing_access_token", 400)
    items, err2 = list_models(api_base, token)
    if err2:
        return _err(request, err2, err2, 400)
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
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    owner_portal_id = _kb_storage_portal_id(db, portal_id)
    aud = (body.audience or "staff").strip().lower()
    if aud not in ("staff", "client"):
        aud = "staff"
    result = create_url_source(db, owner_portal_id, body.url, body.title, audience=aud)
    if not result.get("ok"):
        err = str(result.get("error") or "source_create_failed")
        return _err(request, err, err, 400)
    # enqueue job
    try:
        from redis import Redis
        from rq import Queue
        s = get_settings()
        r = Redis(host=s.redis_host, port=s.redis_port)
        q = Queue(s.rq_ingest_queue_name or "ingest", connection=r)
        source_job_id = int(result.get("job_id") or 0)
        if source_job_id <= 0:
            raise ValueError("missing_job_id")
        q.enqueue(
            "apps.worker.jobs.process_kb_job",
            source_job_id,
            job_id=f"kbjob:{source_job_id}",
            job_timeout=max(300, int(s.kb_job_timeout_seconds or 3600)),
        )
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
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    scope_portal_ids = _account_scope_portal_ids(db, portal_id)
    portal = db.get(Portal, int(portal_id))
    if portal and portal.account_id:
        q = select(KBSource).where(
            sa.or_(
                KBSource.account_id == int(portal.account_id),
                sa.and_(KBSource.account_id.is_(None), KBSource.portal_id.in_(_account_scope_portal_ids(db, portal_id))),
            )
        ).order_by(KBSource.id.desc()).limit(200)
    else:
        q = select(KBSource).where(KBSource.portal_id.in_(scope_portal_ids)).order_by(KBSource.id.desc()).limit(200)
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
            "audience": s.audience or "staff",
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        })
    return JSONResponse({"items": items})


@router.put("/portals/{portal_id}/access/users")
async def put_portal_access_users(
    portal_id: int,
    body: AccessUsersBody,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    """Bulk replace allowlist. user_ids — список Bitrix user ID."""
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    prev_rows = db.execute(
        select(PortalUsersAccess.user_id).where(
            PortalUsersAccess.portal_id == portal_id,
            PortalUsersAccess.kind == "bitrix",
        )
    ).scalars().all()
    prev_set = set(str(u) for u in prev_rows)
    items = body.items or []
    if not items and body.user_ids:
        items = [AccessUserItem(user_id=int(uid)) for uid in body.user_ids]
    user_ids_str = [str(it.user_id) for it in items]
    new_set = set(user_ids_str)

    db.execute(delete(PortalUsersAccess).where(
        PortalUsersAccess.portal_id == portal_id,
        PortalUsersAccess.kind == "bitrix",
    ))
    seen_tg: set[str] = set()
    for it in items:
        uname = normalize_telegram_username(it.telegram_username)
        if uname:
            if uname in seen_tg:
                return _err(request, "duplicate_telegram_username", "duplicate_telegram_username", 400, detail=uname)
            seen_tg.add(uname)
        db.add(PortalUsersAccess(
            portal_id=portal_id,
            user_id=str(it.user_id),
            telegram_username=uname,
            kind="bitrix",
        ))
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


@router.post("/portals/{portal_id}/access/web-users")
async def add_portal_web_user(
    portal_id: int,
    body: WebAccessUserBody,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name_required")
    uname = normalize_telegram_username(body.telegram_username)
    rec = PortalUsersAccess(
        portal_id=portal_id,
        user_id=f"webu_{uuid.uuid4().hex[:10]}",
        display_name=name,
        telegram_username=uname,
        kind="web",
    )
    db.add(rec)
    db.commit()
    return JSONResponse({"status": "ok", "id": rec.user_id})


@router.delete("/portals/{portal_id}/access/web-users/{user_id}")
async def delete_portal_web_user(
    portal_id: int,
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
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
    return JSONResponse({"status": "ok"})


@router.post("/install")
async def bitrix_install_post(request: Request, db: Session = Depends(get_db)):
    """Fallback: Bitrix POST с AUTH_ID в query/form. Если нет токена — отдаём HTML UI."""
    merged = await parse_bitrix_body(request)
    tid = _trace_id(request)
    is_json = _is_json_api_request(request)
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
    if not domain or not access_token:
        if not is_json:
            return _html_ui_response(_load_install_html())
        return JSONResponse(
            {"error": "Missing domain or access_token", "status": "error", "trace_id": tid},
            status_code=400,
        )
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
    logger.info(
        "bitrix_install_payload %s",
        json.dumps(
            {
                "trace_id": tid,
                "portal_id": portal.id,
                "is_json": is_json,
                "has_local_client_id": bool(local_client_id),
                "has_local_client_secret": bool(local_client_secret),
                "merged_keys": sorted([k for k in merged.keys() if k and k.upper() not in {"AUTH_ID", "REFRESH_ID", "ACCESS_TOKEN", "REFRESH_TOKEN"}])[:50],
            },
            ensure_ascii=False,
        ),
    )
    portal_token = create_portal_token_with_user(portal.id, user_id, expires_minutes=15)
    if not is_json:
        return _html_ui_response(_load_install_html())
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
        return JSONResponse(
            error_envelope(
                code="forbidden",
                message="Forbidden",
                trace_id=_trace_id(request),
                legacy_error=True,
            ),
            status_code=403,
        )
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
            error_envelope(
                code="internal_error",
                message="Внутренняя ошибка сервера",
                trace_id=trace_id,
                detail=safe_err,
                legacy_error=True,
            ),
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
        domain = (auth.get("domain") or auth.get("DOMAIN") or "").strip()
        if not domain:
            return JSONResponse({"status": "ok", "event": event, "trace_id": tid})
    if event == "ONIMBOTMESSAGEADD":
        result = process_imbot_message(db, data, auth)
        return JSONResponse(result)
    return JSONResponse({"status": "ok", "event": event, "trace_id": tid})


@router.post("/placement")
async def bitrix_placement(request: Request):
    return JSONResponse({"status": "ok"})

