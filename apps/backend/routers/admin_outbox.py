"""Админские endpoints для outbox."""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.backend.deps import get_db
from apps.backend.auth import get_current_admin
from apps.backend.models.outbox import Outbox

router = APIRouter()


@router.get("")
def list_outbox(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    q = select(Outbox)
    if status:
        q = q.where(Outbox.status == status)
    q = q.offset(skip).limit(limit).order_by(Outbox.id.desc())
    items = db.execute(q).scalars().all()
    return {"items": [{"id": o.id, "portal_id": o.portal_id, "status": o.status} for o in items]}


@router.post("/{id}/retry")
def retry_outbox(
    id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    o = db.get(Outbox, id)
    if not o:
        raise HTTPException(status_code=404, detail="Outbox не найден")
    o.status = "created"
    o.retry_count += 1
    db.commit()
    return {"id": o.id, "status": o.status}
