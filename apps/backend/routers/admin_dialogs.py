"""Админские endpoints для диалогов и сообщений."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from apps.backend.deps import get_db
from apps.backend.auth import get_current_admin
from apps.backend.models.dialog import Dialog, Message
from apps.backend.models.portal import Portal

router = APIRouter()


@router.get("")
def list_dialogs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    portal_id: int | None = Query(None),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    q = select(Dialog)
    if portal_id:
        q = q.where(Dialog.portal_id == portal_id)
    q = q.offset(skip).limit(limit).order_by(Dialog.id.desc())
    dialogs = db.execute(q).scalars().all()
    return {"items": [{"id": d.id, "portal_id": d.portal_id, "provider_dialog_id": d.provider_dialog_id} for d in dialogs]}


@router.get("/{dialog_id}")
def get_dialog(
    dialog_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    d = db.get(Dialog, dialog_id)
    if not d:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    return {
        "id": d.id,
        "portal_id": d.portal_id,
        "provider_dialog_id": d.provider_dialog_id,
        "provider_dialog_id_raw": d.provider_dialog_id_raw,
    }


@router.get("/{dialog_id}/messages")
def get_dialog_messages(
    dialog_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    d = db.get(Dialog, dialog_id)
    if not d:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    q = select(Message).where(Message.dialog_id == dialog_id).order_by(Message.id).offset(skip).limit(limit)
    msgs = db.execute(q).scalars().all()
    return {
        "dialog_id": dialog_id,
        "items": [{"id": m.id, "direction": m.direction, "body": m.body} for m in msgs],
    }
