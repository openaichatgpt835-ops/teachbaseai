"""Helpers for account/workspace identity."""
from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.backend.models.account import Account


def slugify_workspace(value: str | None, *, fallback: str = "workspace") -> str:
    raw = (value or "").strip()
    if not raw:
        return fallback
    normalized = unicodedata.normalize("NFKD", raw)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return slug or fallback


def build_unique_account_slug(
    db: Session,
    name: str | None,
    *,
    fallback: str = "workspace",
    exclude_account_id: int | None = None,
) -> str:
    base = slugify_workspace(name, fallback=fallback)
    existing = {
        str(row[0]).strip().lower()
        for row in db.execute(select(Account.slug).where(Account.slug.is_not(None))).all()
        if row[0]
    }
    if exclude_account_id:
        current = db.execute(
            select(Account.slug).where(Account.id == exclude_account_id, Account.slug.is_not(None))
        ).scalar_one_or_none()
        if current:
            existing.discard(str(current).strip().lower())
    if base not in existing:
        return base
    suffix = 2
    while True:
        candidate = f"{base}-{suffix}"
        if candidate not in existing:
            return candidate
        suffix += 1
