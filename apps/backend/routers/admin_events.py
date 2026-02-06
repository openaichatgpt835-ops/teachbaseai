"""Админские endpoints для событий."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.backend.deps import get_db
from apps.backend.auth import get_current_admin
from apps.backend.models.event import Event

router = APIRouter()


@router.get("")
def list_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    portal_id: int | None = Query(None),
    event_type: str | None = Query(None, description="e.g. install_step"),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    q = select(Event)
    if portal_id:
        q = q.where(Event.portal_id == portal_id)
    if event_type:
        q = q.where(Event.event_type == event_type)
    q = q.offset(skip).limit(limit).order_by(Event.id.desc())
    events = db.execute(q).scalars().all()
    return {"items": [{"id": e.id, "portal_id": e.portal_id, "event_type": e.event_type} for e in events]}
