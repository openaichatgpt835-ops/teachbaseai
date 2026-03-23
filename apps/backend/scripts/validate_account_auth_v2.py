"""Validate account-centric auth invariants."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.backend.database import get_session_factory
from apps.backend.models.account import Account, AccountMembership, AppUserWebCredential
from apps.backend.models.portal import Portal


@dataclass
class ValidationResult:
    ok: bool = True
    accounts_without_slug: list[int] = field(default_factory=list)
    duplicate_slugs: list[str] = field(default_factory=list)
    portals_without_account: list[int] = field(default_factory=list)
    accounts_without_owner: list[int] = field(default_factory=list)
    owners_without_membership: list[int] = field(default_factory=list)
    credentials_without_email: list[int] = field(default_factory=list)


def run(db: Session) -> ValidationResult:
    result = ValidationResult()
    try:
        accounts = db.execute(select(Account).order_by(Account.id.asc())).scalars().all()
        slug_seen: set[str] = set()
        for account in accounts:
            slug = (account.slug or "").strip().lower()
            if not slug:
                result.accounts_without_slug.append(int(account.id))
            elif slug in slug_seen:
                result.duplicate_slugs.append(slug)
            else:
                slug_seen.add(slug)

            if not account.owner_user_id:
                result.accounts_without_owner.append(int(account.id))
            else:
                membership = db.execute(
                    select(AccountMembership).where(
                        AccountMembership.account_id == int(account.id),
                        AccountMembership.user_id == int(account.owner_user_id),
                        AccountMembership.role == "owner",
                        AccountMembership.status.in_(["active", "invited"]),
                    )
                ).scalar_one_or_none()
                if not membership:
                    result.owners_without_membership.append(int(account.id))

        portals = db.execute(select(Portal.id, Portal.domain, Portal.install_type, Portal.account_id)).all()
        for portal_id, domain, install_type, account_id in portals:
            domain_l = (domain or "").strip().lower()
            install_type_l = (install_type or "").strip().lower()
            if install_type_l == "web" or "bitrix24." in domain_l or domain_l.startswith("web:"):
                if account_id is None:
                    result.portals_without_account.append(int(portal_id))

        creds = db.execute(select(AppUserWebCredential.user_id, AppUserWebCredential.login, AppUserWebCredential.email)).all()
        for user_id, login, email in creds:
            if not ((email or "").strip() or (login or "").strip()):
                result.credentials_without_email.append(int(user_id))

        result.ok = not any(
            (
                result.accounts_without_slug,
                result.duplicate_slugs,
                result.portals_without_account,
                result.accounts_without_owner,
                result.owners_without_membership,
                result.credentials_without_email,
            )
        )
        return result
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate account-centric auth invariants")
    _ = parser.parse_args()
    session_factory = get_session_factory()
    db: Session = session_factory()
    result = run(db)
    print(json.dumps(asdict(result), ensure_ascii=False))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
