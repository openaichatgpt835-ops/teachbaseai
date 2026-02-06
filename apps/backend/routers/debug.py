"""Debug endpoints (только admin + флаг)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.backend.deps import get_db
from apps.backend.auth import get_current_admin
from apps.backend.config import get_settings
from apps.backend.models.portal import Portal
from apps.backend.models.dialog import Dialog, Message
from apps.backend.models.event import Event
from apps.backend.models.outbox import Outbox

router = APIRouter()


class SimulateBitrixIncomingRequest(BaseModel):
    portal_id: int = 1
    dialog_id_raw: str = "chat123"
    message_id: str = "msg1"
    body: str = "ping"


def _respond_body(body: str) -> str:
    if body.strip().lower() == "ping":
        return "pong"
    return "ок"


@router.post("/simulate/bitrix/incoming")
def simulate_bitrix_incoming(
    data: SimulateBitrixIncomingRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    s = get_settings()
    if not s.debug_endpoints_enabled:
        raise HTTPException(status_code=403, detail="Debug endpoints отключены")

    portal = db.get(Portal, data.portal_id)
    if not portal:
        portal = Portal(domain=f"sim-{data.portal_id}.bitrix24.ru", status="active")
        db.add(portal)
        db.commit()
        db.refresh(portal)

    dialog_id_norm = data.dialog_id_raw
    dialog = db.execute(
        select(Dialog).where(
            Dialog.portal_id == portal.id,
            Dialog.provider_dialog_id == dialog_id_norm,
        )
    ).scalar_one_or_none()
    if not dialog:
        dialog = Dialog(
            portal_id=portal.id,
            provider_dialog_id=dialog_id_norm,
            provider_dialog_id_raw=data.dialog_id_raw,
        )
        db.add(dialog)
        db.commit()
        db.refresh(dialog)

    event = Event(
        portal_id=portal.id,
        provider_event_id=data.message_id,
        event_type="rx",
        payload_json=f'{{"body":"{data.body}"}}',
    )
    db.add(event)
    db.commit()

    msg_rx = Message(
        dialog_id=dialog.id,
        provider_message_id=data.message_id,
        direction="rx",
        body=data.body,
    )
    db.add(msg_rx)
    db.commit()
    db.refresh(msg_rx)

    response_body = _respond_body(data.body)
    msg_tx = Message(
        dialog_id=dialog.id,
        provider_message_id=f"{data.message_id}_tx",
        direction="tx",
        body=response_body,
    )
    db.add(msg_tx)
    db.commit()
    db.refresh(msg_tx)

    outbox = Outbox(
        portal_id=portal.id,
        message_id=msg_tx.id,
        status="sent",
        payload_json=f'{{"body":"{response_body}"}}',
    )
    db.add(outbox)
    db.commit()

    return {
        "status": "ok",
        "dialog_id": dialog.id,
        "message_rx_id": msg_rx.id,
        "message_tx_id": msg_tx.id,
        "response": response_body,
    }
