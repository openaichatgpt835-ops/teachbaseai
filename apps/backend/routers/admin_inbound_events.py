"""Admin: inbound events (list, detail, usage, prune)."""
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select, desc, func

from apps.backend.auth import get_current_admin
from apps.backend.deps import get_db
from apps.backend.models.bitrix_inbound_event import BitrixInboundEvent
from apps.backend.services.bitrix_inbound_log import get_usage, run_prune
from apps.backend.services.inbound_settings import get_inbound_settings

router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.get("/inbound-events/usage")
def get_inbound_events_usage(db: Session = Depends(get_db)):
    """Storage usage: used_mb, target_budget_mb, percent, approx_rows, oldest_at, newest_at."""
    settings = get_inbound_settings(db)
    return get_usage(db, settings)


class PruneBody(BaseModel):
    mode: str = Field("auto", description="auto | all | older_than_days")
    older_than_days: int | None = Field(None, ge=1, le=365, description="For mode=older_than_days")


@router.post("/inbound-events/prune")
def post_inbound_events_prune(
    body: PruneBody | None = None,
    db: Session = Depends(get_db),
):
    """Run prune: mode=auto (retention+max_rows), all (delete all), older_than_days (param older_than_days)."""
    mode = (body.mode if body else "auto") or "auto"
    if mode not in ("auto", "all", "older_than_days"):
        raise HTTPException(status_code=400, detail="mode must be auto, all, or older_than_days")
    older_than_days = body.older_than_days if body and body.mode == "older_than_days" else None
    if mode == "older_than_days" and older_than_days is None:
        raise HTTPException(status_code=400, detail="older_than_days required for mode=older_than_days")
    settings = get_inbound_settings(db)
    result = run_prune(db, mode, older_than_days=older_than_days, settings=settings)
    return result


@router.get("/inbound-events")
def list_inbound_events(
    db: Session = Depends(get_db),
    portal_id: int | None = Query(None),
    domain: str | None = Query(None),
    trace_id: str | None = Query(None),
    since: str | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
):
    """List last inbound events (no heavy fields). Filters: portal_id, domain, trace_id, since (ISO)."""
    q = select(BitrixInboundEvent).order_by(desc(BitrixInboundEvent.created_at)).limit(limit)
    if portal_id is not None:
        q = q.where(BitrixInboundEvent.portal_id == portal_id)
    if domain:
        q = q.where(BitrixInboundEvent.domain == domain)
    if trace_id:
        q = q.where(BitrixInboundEvent.trace_id == trace_id)
    if since:
        try:
            from datetime import datetime
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            q = q.where(BitrixInboundEvent.created_at >= since_dt)
        except ValueError:
            pass
    rows = db.execute(q).scalars().all()
    items = []
    for r in rows:
        user_agent = None
        if r.headers_json and isinstance(r.headers_json, dict):
            user_agent = (r.headers_json.get("user-agent") or r.headers_json.get("User-Agent") or "")[:256]
        items.append({
            "id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "portal_id": r.portal_id,
            "domain": r.domain,
            "member_id": r.member_id,
            "dialog_id": r.dialog_id,
            "user_id": r.user_id,
            "event_name": r.event_name,
            "trace_id": r.trace_id,
            "user_agent": user_agent,
            "content_type": r.content_type,
            "body_truncated": r.body_truncated,
            "hints_json": r.hints_json,
            "method": r.method,
            "path": r.path,
        })
    return {"items": items, "total": len(items)}


@router.get("/inbound-events/{event_id}")
def get_inbound_event(event_id: int, db: Session = Depends(get_db)):
    """Detail one inbound event. No raw body."""
    r = db.execute(select(BitrixInboundEvent).where(BitrixInboundEvent.id == event_id)).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    return {
        "id": r.id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "trace_id": r.trace_id,
        "portal_id": r.portal_id,
        "domain": r.domain,
        "member_id": r.member_id,
        "dialog_id": r.dialog_id,
        "user_id": r.user_id,
        "event_name": r.event_name,
        "remote_ip": r.remote_ip,
        "method": r.method,
        "path": r.path,
        "query": r.query,
        "content_type": r.content_type,
        "headers_json": r.headers_json,
        "body_preview": r.body_preview,
        "body_truncated": r.body_truncated,
        "body_sha256": r.body_sha256,
        "parsed_redacted_json": r.parsed_redacted_json,
        "hints_json": r.hints_json,
        "status_hint": r.status_hint,
    }
