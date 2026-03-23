"""Backfill account-centric auth foundation.

Creates missing account slugs, repairs RBAC links for legacy web users and
mirrors legacy web_sessions into app_sessions for smoother cutover.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.backend.database import get_session_factory
from apps.backend.models.account import Account, AppSession
from apps.backend.models.portal import Portal
from apps.backend.models.web_user import WebSession, WebUser
from apps.backend.services.account_workspace import build_unique_account_slug
from apps.backend.services.rbac_service import ensure_rbac_for_web_user


@dataclass
class BackfillStats:
    accounts_total: int = 0
    accounts_slugged: int = 0
    web_users_total: int = 0
    web_users_processed: int = 0
    sessions_total: int = 0
    sessions_mirrored: int = 0
    failed: int = 0


def run(db: Session, *, commit: bool = False) -> BackfillStats:
    stats = BackfillStats()
    now = datetime.utcnow()

    try:
        accounts = db.execute(select(Account).order_by(Account.id.asc())).scalars().all()
        stats.accounts_total = len(accounts)
        for account in accounts:
            if (account.slug or "").strip():
                continue
            account.slug = build_unique_account_slug(
                db,
                account.name,
                fallback=f"workspace-{int(account.account_no or account.id)}",
                exclude_account_id=int(account.id),
            )
            account.updated_at = now
            db.add(account)
            stats.accounts_slugged += 1

        web_users = db.execute(select(WebUser).order_by(WebUser.id.asc())).scalars().all()
        stats.web_users_total = len(web_users)
        for web_user in web_users:
            try:
                if not web_user.portal_id:
                    continue
                portal = db.get(Portal, int(web_user.portal_id))
                if not portal:
                    continue
                _account_id, app_user_id = ensure_rbac_for_web_user(db, web_user, force_owner=False, account_name=None)
                if app_user_id:
                    sessions = db.execute(
                        select(WebSession).where(WebSession.user_id == int(web_user.id))
                    ).scalars().all()
                    for session in sessions:
                        if int(session.app_user_id or 0) != int(app_user_id):
                            session.app_user_id = int(app_user_id)
                            db.add(session)
                stats.web_users_processed += 1
            except Exception:
                stats.failed += 1

        existing_app_sessions = {
            str(token)
            for token in db.execute(select(AppSession.token)).scalars().all()
            if token
        }
        web_sessions = db.execute(select(WebSession).order_by(WebSession.id.asc())).scalars().all()
        stats.sessions_total = len(web_sessions)
        for session in web_sessions:
            try:
                if not session.app_user_id or not session.token or session.token in existing_app_sessions:
                    continue
                web_user = db.get(WebUser, int(session.user_id))
                if not web_user:
                    continue
                active_account_id = None
                if web_user.portal_id:
                    portal = db.get(Portal, int(web_user.portal_id))
                    if portal and portal.account_id:
                        active_account_id = int(portal.account_id)
                db.add(
                    AppSession(
                        user_id=int(session.app_user_id),
                        active_account_id=active_account_id,
                        token=str(session.token),
                        created_at=session.created_at or now,
                        expires_at=session.expires_at,
                    )
                )
                existing_app_sessions.add(str(session.token))
                stats.sessions_mirrored += 1
            except Exception:
                stats.failed += 1

        if commit:
            db.commit()
        else:
            db.rollback()
        return stats
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill account-centric auth foundation")
    parser.add_argument("--commit", action="store_true", help="Apply changes (default: dry-run)")
    args = parser.parse_args()

    session_factory = get_session_factory()
    db = session_factory()
    stats = run(db, commit=args.commit)
    print(
        json.dumps(
            {
                "status": "ok" if stats.failed == 0 else "warning",
                "dry_run": not args.commit,
                "accounts_total": stats.accounts_total,
                "accounts_slugged": stats.accounts_slugged,
                "web_users_total": stats.web_users_total,
                "web_users_processed": stats.web_users_processed,
                "sessions_total": stats.sessions_total,
                "sessions_mirrored": stats.sessions_mirrored,
                "failed": stats.failed,
            },
            ensure_ascii=False,
        )
    )
    return 0 if stats.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
