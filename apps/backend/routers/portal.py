"""Portal admin API (внутри Bitrix placement)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from apps.backend.config import get_settings

router = APIRouter()


@router.get("/status")
def portal_status():
    s = get_settings()
    return {
        "status": "ok",
        "public_base_url": s.public_base_url or "ожидается PUBLIC_BASE_URL",
    }


@router.get("/settings")
def portal_settings():
    return {"allowed_users": [], "kb_uploaded": False}


class AllowedUsersRequest(BaseModel):
    user_ids: list[str]


@router.post("/settings/allowed-users")
def set_allowed_users(data: AllowedUsersRequest):
    return {"status": "ok", "count": len(data.user_ids)}


@router.post("/kb/upload")
def kb_upload():
    return {"status": "ok", "message": "KB загружена"}


@router.post("/kb/reindex")
def kb_reindex():
    return {"status": "ok"}


@router.post("/chats/provision")
def provision_chats():
    return {"status": "ok"}


@router.post("/setup")
def portal_setup():
    return {"status": "ok"}
