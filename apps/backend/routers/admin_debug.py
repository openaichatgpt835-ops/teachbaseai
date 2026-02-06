"""Admin-only debug endpoints (DEBUG_ENDPOINTS_ENABLED=1)."""
import uuid
from fastapi import APIRouter, Depends, HTTPException

from apps.backend.auth import get_current_admin
from apps.backend.config import get_settings

router = APIRouter()


@router.post("/install/finalize_mock")
def admin_install_finalize_mock(_: dict = Depends(get_current_admin)):
    """Возвращает 200 JSON без вызова Bitrix (для проверки XHR JSON-контракта)."""
    s = get_settings()
    if not s.debug_endpoints_enabled:
        raise HTTPException(status_code=403, detail="Debug endpoints отключены")
    trace_id = str(uuid.uuid4())[:16]
    return {
        "status": "ok",
        "trace_id": trace_id,
        "steps": {"allowlist": "ok", "ensure_bot": "ok", "provision": {"status": "ok", "total": 0, "ok": 0, "failed": []}},
    }
