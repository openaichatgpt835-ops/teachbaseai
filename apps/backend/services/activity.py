"""Activity logging helpers."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy.orm import Session

from apps.backend.models.activity_event import ActivityEvent


def log_activity(
    db: Session,
    *,
    kind: str,
    portal_id: int | None = None,
    web_user_id: int | None = None,
) -> None:
    row = ActivityEvent(
        kind=kind,
        portal_id=portal_id,
        web_user_id=web_user_id,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
