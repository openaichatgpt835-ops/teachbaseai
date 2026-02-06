"""Admin: Bitrix HTTP traces."""
import json
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from apps.backend.auth import get_current_admin
from apps.backend.deps import get_db
from apps.backend.models.bitrix_log import BitrixHttpLog

router = APIRouter(dependencies=[Depends(get_current_admin)])


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
