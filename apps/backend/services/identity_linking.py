"""Safe identity linking for multi-account users."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.backend.models.account import (
    AccountIntegration,
    AppUser,
    AppUserIdentity,
    AppUserWebCredential,
)


@dataclass
class IdentityLinkResult:
    status: str
    user_id: int | None
    identity_id: int | None
    account_id: int | None
    matched_user_id: int | None = None
    reason: str | None = None


def _normalize_email(email: str | None) -> str | None:
    value = (email or "").strip().lower()
    return value or None


def _create_identity(
    db: Session,
    *,
    user_id: int,
    provider: str,
    integration_id: int | None,
    external_id: str,
    display_value: str | None,
    meta_json: dict | None = None,
) -> AppUserIdentity:
    ident = AppUserIdentity(
        user_id=int(user_id),
        provider=provider,
        integration_id=int(integration_id) if integration_id else None,
        external_id=str(external_id),
        display_value=(display_value or "").strip() or None,
        meta_json=meta_json,
        created_at=datetime.utcnow(),
    )
    db.add(ident)
    db.flush()
    return ident


def link_or_create_app_user(
    db: Session,
    *,
    provider: str,
    integration_id: int | None,
    external_id: str,
    display_value: str | None = None,
    email: str | None = None,
    expected_app_user_id: int | None = None,
    auto_create_user: bool = True,
    meta_json: dict | None = None,
) -> IdentityLinkResult:
    provider_norm = (provider or "").strip().lower()
    external_norm = str(external_id or "").strip()
    if not provider_norm or not external_norm:
        return IdentityLinkResult(
            status="invalid_input",
            user_id=None,
            identity_id=None,
            account_id=None,
            reason="missing_provider_or_external_id",
        )

    account_id: int | None = None
    if integration_id:
        integ = db.get(AccountIntegration, int(integration_id))
        account_id = int(integ.account_id) if integ and integ.account_id else None

    existing = db.execute(
        select(AppUserIdentity).where(
            AppUserIdentity.provider == provider_norm,
            AppUserIdentity.integration_id == (int(integration_id) if integration_id else None),
            AppUserIdentity.external_id == external_norm,
        )
    ).scalar_one_or_none()
    if existing:
        updated = False
        if display_value and (existing.display_value or "").strip() != display_value.strip():
            existing.display_value = display_value.strip()
            updated = True
        if meta_json is not None:
            existing.meta_json = meta_json
            updated = True
        if updated:
            db.add(existing)
            db.flush()
        return IdentityLinkResult(
            status="existing_identity",
            user_id=int(existing.user_id),
            identity_id=int(existing.id),
            account_id=account_id,
        )

    if expected_app_user_id:
        ident = _create_identity(
            db,
            user_id=int(expected_app_user_id),
            provider=provider_norm,
            integration_id=integration_id,
            external_id=external_norm,
            display_value=display_value,
            meta_json=meta_json,
        )
        return IdentityLinkResult(
            status="linked_expected_user",
            user_id=int(expected_app_user_id),
            identity_id=int(ident.id),
            account_id=account_id,
        )

    email_norm = _normalize_email(email)
    if email_norm:
        cred = db.execute(
            select(AppUserWebCredential).where(AppUserWebCredential.email == email_norm)
        ).scalar_one_or_none()
        if cred:
            ident = _create_identity(
                db,
                user_id=int(cred.user_id),
                provider=provider_norm,
                integration_id=integration_id,
                external_id=external_norm,
                display_value=display_value,
                meta_json=meta_json,
            )
            return IdentityLinkResult(
                status="linked_by_email",
                user_id=int(cred.user_id),
                identity_id=int(ident.id),
                account_id=account_id,
                matched_user_id=int(cred.user_id),
            )

    if not auto_create_user:
        return IdentityLinkResult(
            status="unresolved",
            user_id=None,
            identity_id=None,
            account_id=account_id,
            reason="no_safe_match",
        )

    app_user = AppUser(
        display_name=(display_value or email_norm or f"{provider_norm}:{external_norm}").strip(),
        status="active",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(app_user)
    db.flush()
    ident = _create_identity(
        db,
        user_id=int(app_user.id),
        provider=provider_norm,
        integration_id=integration_id,
        external_id=external_norm,
        display_value=display_value,
        meta_json=meta_json,
    )
    return IdentityLinkResult(
        status="created_user",
        user_id=int(app_user.id),
        identity_id=int(ident.id),
        account_id=account_id,
    )
