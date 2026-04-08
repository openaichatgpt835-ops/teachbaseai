"""Public billing endpoints for provider callbacks."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from apps.backend.deps import get_db
from apps.backend.services.billing_payments import handle_yookassa_webhook

router = APIRouter()


@router.post("/yookassa/webhook")
async def yookassa_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid_json") from exc
    try:
        return handle_yookassa_webhook(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
