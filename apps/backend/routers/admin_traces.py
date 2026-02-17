"""Admin: Bitrix HTTP traces."""
import json
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from apps.backend.auth import get_current_admin
from apps.backend.deps import get_db
from apps.backend.models.bitrix_log import BitrixHttpLog
from apps.backend.models.bitrix_inbound_event import BitrixInboundEvent
from apps.backend.models.outbox import Outbox

router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.get("/{trace_id}/timeline")
def get_trace_timeline(trace_id: str, db: Session = Depends(get_db)):
    items: list[dict] = []

    log_rows = db.execute(
        select(BitrixHttpLog)
        .where(BitrixHttpLog.trace_id == trace_id)
        .order_by(BitrixHttpLog.created_at)
    ).scalars().all()
    for r in log_rows:
        items.append({
            "source": "bitrix_http",
            "id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "portal_id": r.portal_id,
            "kind": r.kind,
            "status": r.status_code,
            "summary": r.path or "",
        })

    inbound_rows = db.execute(
        select(BitrixInboundEvent)
        .where(BitrixInboundEvent.trace_id == trace_id)
        .order_by(BitrixInboundEvent.created_at)
    ).scalars().all()
    for r in inbound_rows:
        items.append({
            "source": "inbound",
            "id": int(r.id),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "portal_id": r.portal_id,
            "kind": r.event_name,
            "status": r.status_hint,
            "summary": r.path or "",
        })

    outbox_rows = db.execute(select(Outbox).order_by(Outbox.created_at.desc()).limit(1000)).scalars().all()
    for r in outbox_rows:
        payload = {}
        if r.payload_json:
            try:
                payload = json.loads(r.payload_json) if isinstance(r.payload_json, str) else (r.payload_json or {})
            except Exception:
                payload = {}
        if str(payload.get("trace_id") or "") != trace_id:
            continue
        items.append({
            "source": "outbox",
            "id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "portal_id": r.portal_id,
            "kind": payload.get("kind") or "outbox",
            "status": r.status,
            "summary": (r.error_message or "")[:200],
        })

    if not items:
        raise HTTPException(status_code=404, detail="Трейс не найден")

    def _sort_key(x: dict):
        return x.get("created_at") or ""

    items.sort(key=_sort_key)
    return {"trace_id": trace_id, "items": items}


@router.get("/{trace_id}")
def get_trace_detail(trace_id: str, db: Session = Depends(get_db)):
    """Детали трейса по trace_id: все записи bitrix_http_logs (без токенов)."""
    q = (
        select(BitrixHttpLog)
        .where(BitrixHttpLog.trace_id == trace_id)
        .order_by(BitrixHttpLog.created_at)
    )
    rows = db.execute(q).scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail="Трейс не найден")
    items = []
    for r in rows:
        summary = {}
        if r.summary_json:
            try:
                summary = json.loads(r.summary_json) if isinstance(r.summary_json, str) else r.summary_json
            except Exception:
                pass
        req = summary.get("request_shape_json") or {}
        resp = summary.get("response_shape_json") or {}
        request_json = summary.get("request_json")
        response_json = summary.get("response_json")
        headers_min = summary.get("headers_min")
        items.append({
            "id": r.id,
            "trace_id": r.trace_id,
            "portal_id": r.portal_id,
            "direction": r.direction,
            "kind": r.kind,
            "method": r.method,
            "path": r.path,
            "status_code": r.status_code,
            "latency_ms": r.latency_ms,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "bitrix_error_code": summary.get("bitrix_error_code") or summary.get("error_code") or resp.get("bitrix_error_code"),
            "bitrix_error_desc": summary.get("bitrix_error_desc") or summary.get("error_description_safe") or resp.get("bitrix_error_desc"),
            "event_message_add_url": req.get("event_message_add_url"),
            "content_type_sent": req.get("content_type_sent"),
            "sent_keys": req.get("sent_keys"),
            "top_level_name_enabled": req.get("has_NAME_top_level"),
            "api_prefix_used": req.get("api_prefix_used"),
            "event_urls_sent": summary.get("event_urls_sent"),
            "request_json": request_json,
            "response_json": response_json,
            "headers_min": headers_min,
            "summary": summary,
        })
    return {"trace_id": trace_id, "items": items}


@router.get("")
def list_traces(
    db: Session = Depends(get_db),
    portal_id: int | None = Query(None),
    trace_id: str | None = Query(None),
    limit: int = Query(100, le=500),
):
    q = select(BitrixHttpLog).order_by(desc(BitrixHttpLog.created_at)).limit(limit)
    if portal_id:
        q = q.where(BitrixHttpLog.portal_id == portal_id)
    if trace_id:
        q = q.where(BitrixHttpLog.trace_id == trace_id)
    rows = db.execute(q).scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "trace_id": r.trace_id,
                "portal_id": r.portal_id,
                "direction": r.direction,
                "kind": r.kind,
                "method": r.method,
                "path": r.path,
                "summary": r.summary_json,
                "status_code": r.status_code,
                "latency_ms": r.latency_ms,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }
