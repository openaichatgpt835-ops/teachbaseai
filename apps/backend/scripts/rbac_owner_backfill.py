"""One-off RBAC owner backfill/repair for existing web users."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.backend.database import get_session_factory
from apps.backend.models.portal import Portal
from apps.backend.models.web_user import WebUser
from apps.backend.services.rbac_service import ensure_rbac_for_web_user


@dataclass
class BackfillStats:
    total_users: int = 0
    owners_forced: int = 0
    processed: int = 0
    failed: int = 0


def _is_owner_by_portal(portal: Portal, web_user: WebUser, db: Session) -> bool:
    if (portal.install_type or "").strip().lower() == "web":
        return True

    if portal.admin_user_id and int(portal.admin_user_id) == int(web_user.id):
        return True

    owner_email = None
    try:
        meta = json.loads(portal.metadata_json or "{}") if portal.metadata_json else {}
        owner_email = (meta.get("owner_email") or "").strip().lower() or None
    except Exception:
        owner_email = None
    if owner_email and owner_email == (web_user.email or "").strip().lower():
        return True

    # Fallback: single web user on portal => owner.
    peers = db.execute(
        select(WebUser.id).where(WebUser.portal_id == portal.id)
    ).all()
    return len(peers) <= 1


def run(commit: bool = False) -> BackfillStats:
    SessionLocal = get_session_factory()
    db: Session = SessionLocal()
    stats = BackfillStats()
    try:
        users = db.execute(select(WebUser).order_by(WebUser.id.asc())).scalars().all()
        stats.total_users = len(users)
        for wu in users:
            try:
                if not wu.portal_id:
                    continue
                portal = db.get(Portal, int(wu.portal_id))
                if not portal:
                    continue

                owner_mode = _is_owner_by_portal(portal, wu, db)
                if owner_mode:
                    stats.owners_forced += 1
                ensure_rbac_for_web_user(
                    db,
                    wu,
                    force_owner=owner_mode,
                    account_name=None,
                )
                stats.processed += 1
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
    parser = argparse.ArgumentParser(description="RBAC owner backfill/repair")
    parser.add_argument("--commit", action="store_true", help="Apply changes (default: dry-run)")
    args = parser.parse_args()

    started_at = datetime.utcnow().isoformat()
    stats = run(commit=args.commit)
    print(
        json.dumps(
            {
                "status": "ok",
                "dry_run": not args.commit,
                "started_at": started_at,
                "total_users": stats.total_users,
                "owners_forced": stats.owners_forced,
                "processed": stats.processed,
                "failed": stats.failed,
            },
            ensure_ascii=False,
        )
    )
    return 0 if stats.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
