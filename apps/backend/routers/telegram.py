"""Telegram webhook endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from apps.backend.deps import get_db
from apps.backend.services.telegram_settings import (
    get_portal_telegram_secret,
    get_portal_telegram_token_plain,
    get_portal_telegram_settings,
)
from apps.backend.services.telegram_events import process_telegram_update
from apps.backend.clients.telegram import telegram_send_message

router = APIRouter()
logger = logging.getLogger(__name__)


def _check_secret(request: Request, portal_id: int, kind: str, secret: str, db: Session) -> bool:
    expected = get_portal_telegram_secret(db, portal_id, kind)
    if not expected or expected != secret:
        return False
    header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if header_secret and header_secret != expected:
        return False
    return True


async def _handle_update(request: Request, portal_id: int, kind: str, secret: str, db: Session) -> JSONResponse:
    if not _check_secret(request, portal_id, kind, secret, db):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    settings = get_portal_telegram_settings(db, portal_id)
    if kind == "staff" and not settings.get("staff", {}).get("enabled"):
        return JSONResponse({"ok": True, "disabled": True})
    if kind == "client" and not settings.get("client", {}).get("enabled"):
        return JSONResponse({"ok": True, "disabled": True})
    update = await request.json()
    result = process_telegram_update(db, portal_id, kind, update)
    if result.get("status") == "blocked" and result.get("reply") and result.get("chat_id"):
        token = get_portal_telegram_token_plain(db, portal_id, kind)
        if token:
            telegram_send_message(token, result.get("chat_id"), result.get("reply"))
    return JSONResponse({"ok": True})


@router.post("/staff/{portal_id}/{secret}")
async def telegram_staff_webhook(
    portal_id: int,
    secret: str,
    request: Request,
    db: Session = Depends(get_db),
):
    return await _handle_update(request, portal_id, "staff", secret, db)


@router.post("/client/{portal_id}/{secret}")
async def telegram_client_webhook(
    portal_id: int,
    secret: str,
    request: Request,
    db: Session = Depends(get_db),
):
    return await _handle_update(request, portal_id, "client", secret, db)
