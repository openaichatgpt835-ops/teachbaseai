from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.backend.deps import get_db
from apps.backend.models import PortalBotFlow
from apps.backend.routers.bitrix import _require_portal_admin, require_portal_access
from apps.backend.services.bot_flow_engine import execute_client_flow_preview
from apps.backend.utils.api_errors import error_envelope
from apps.backend.utils.api_schema import is_schema_v2

router = APIRouter()


class BotFlowBody(BaseModel):
    draft_json: dict | None = None


class BotFlowTestBody(BaseModel):
    text: str
    state_json: dict | None = None
    draft_json: dict | None = None


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "") or ""


def _err(request: Request, code: str, message: str, status_code: int, detail: str | None = None) -> JSONResponse:
    return JSONResponse(
        error_envelope(
            code=code,
            message=message,
            trace_id=_trace_id(request),
            detail=detail,
            legacy_error=True,
        ),
        status_code=status_code,
    )


@router.get("/portals/{portal_id}/botflow/client")
async def get_portal_botflow_client(
    portal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    row = db.get(PortalBotFlow, {"portal_id": portal_id, "kind": "client"})
    return JSONResponse({
        "draft": row.draft_json if row else None,
        "published": row.published_json if row else None,
    })


@router.post("/portals/{portal_id}/botflow/client")
async def set_portal_botflow_client(
    portal_id: int,
    body: BotFlowBody,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    row = db.get(PortalBotFlow, {"portal_id": portal_id, "kind": "client"})
    if not row:
        row = PortalBotFlow(portal_id=portal_id, kind="client", draft_json=body.draft_json)
        db.add(row)
    else:
        row.draft_json = body.draft_json
    db.commit()
    return JSONResponse({"status": "ok"})


@router.post("/portals/{portal_id}/botflow/client/publish")
async def publish_portal_botflow_client(
    portal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    row = db.get(PortalBotFlow, {"portal_id": portal_id, "kind": "client"})
    if not row or not row.draft_json:
        return _err(request, "missing_draft", "missing_draft", 400)
    row.published_json = row.draft_json
    db.commit()
    return JSONResponse({"status": "ok"})


@router.post("/portals/{portal_id}/botflow/client/test")
async def test_portal_botflow_client(
    portal_id: int,
    body: BotFlowTestBody,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    _require_portal_admin(db, portal_id, request)
    row = db.get(PortalBotFlow, {"portal_id": portal_id, "kind": "client"})
    flow = body.draft_json or (row.draft_json if row else None)
    if not flow:
        return _err(request, "missing_draft", "missing_draft", 400)
    text, state, trace = execute_client_flow_preview(db, portal_id, 0, body.text, flow, state_override=body.state_json)
    if is_schema_v2(request):
        return JSONResponse({
            "ok": True,
            "data": {
                "answer": text,
                "state": state,
                "trace": trace,
            },
            "meta": {
                "schema": "v2",
                "channel": "bitrix_botflow_test",
            },
        })
    return JSONResponse({"text": text, "state": state, "trace": trace})
