"""Admin: unified API errors feed."""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, JSONResponse
from sqlalchemy import desc, select, func
from sqlalchemy.orm import Session

from apps.backend.auth import get_current_admin
from apps.backend.deps import get_db
from apps.backend.models.bitrix_inbound_event import BitrixInboundEvent
from apps.backend.models.bitrix_log import BitrixHttpLog
from apps.backend.models.outbox import Outbox
from apps.backend.models.portal import Portal

router = APIRouter(dependencies=[Depends(get_current_admin)])


def _safe_json(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def _period_to_since(period: str | None) -> datetime:
    p = (period or "24h").strip().lower()
    now = datetime.now(timezone.utc)
    if p == "1h":
        return now - timedelta(hours=1)
    if p == "7d":
        return now - timedelta(days=7)
    return now - timedelta(hours=24)


@router.get("/errors/summary")
def errors_summary(
    db: Session = Depends(get_db),
    period: str = Query("24h", description="1h | 24h | 7d"),
):
    since_dt = _period_to_since(period)

    total_http = db.execute(
        select(func.count(BitrixHttpLog.id)).where(BitrixHttpLog.created_at >= since_dt)
    ).scalar() or 0
    error_http = db.execute(
        select(func.count(BitrixHttpLog.id)).where(
            BitrixHttpLog.created_at >= since_dt,
            BitrixHttpLog.status_code >= 400,
        )
    ).scalar() or 0
    error_rate = round((float(error_http) / float(total_http) * 100.0), 2) if total_http else 0.0

    q = select(BitrixHttpLog).where(
        BitrixHttpLog.created_at >= since_dt,
        BitrixHttpLog.status_code >= 400,
    ).order_by(desc(BitrixHttpLog.created_at)).limit(5000)
    rows = db.execute(q).scalars().all()
    code_counts: dict[str, int] = {}
    portal_counts: dict[str, int] = {}
    latencies: list[int] = []
    for r in rows:
        s = _safe_json(r.summary_json)
        code = str(s.get("bitrix_error_code") or s.get("error_code") or (f"http_{r.status_code}" if r.status_code else "http_error"))
        code_counts[code] = code_counts.get(code, 0) + 1
        portal_key = str(r.portal_id or 0)
        portal_counts[portal_key] = portal_counts.get(portal_key, 0) + 1
        if r.latency_ms is not None:
            try:
                latencies.append(int(r.latency_ms))
            except Exception:
                pass

    def _top(d: dict[str, int], n: int = 5):
        return [{"key": k, "count": c} for k, c in sorted(d.items(), key=lambda x: x[1], reverse=True)[:n]]

    p95 = 0
    if latencies:
        vals = sorted(latencies)
        idx = max(0, min(len(vals) - 1, int(round(0.95 * (len(vals) - 1)))))
        p95 = int(vals[idx])

    return {
        "period": period,
        "since": since_dt.isoformat(),
        "error_rate_percent": error_rate,
        "bitrix_total_requests": int(total_http),
        "bitrix_error_requests": int(error_http),
        "p95_latency_ms": p95,
        "top_codes": _top(code_counts),
        "top_portals": _top(portal_counts),
    }


@router.get("/errors")
def list_errors(
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    portal_id: int | None = Query(None),
    portal: str | None = Query(None, description="portal_id or partial domain"),
    trace_id: str | None = Query(None),
    channel: str | None = Query(None, description="bitrix_http | inbound | outbox"),
    code: str | None = Query(None, description="substring filter for code"),
):
    items = _collect_errors(
        db=db,
        limit=limit,
        portal_id=portal_id,
        portal=portal,
        trace_id=trace_id,
        channel=channel,
        code=code,
    )
    return {"items": items, "total": len(items)}


def _collect_errors(
    *,
    db: Session,
    limit: int,
    portal_id: int | None,
    portal: str | None,
    trace_id: str | None,
    channel: str | None,
    code: str | None,
) -> list[dict[str, Any]]:
    portal_rows = db.execute(select(Portal.id, Portal.domain)).all()
    portal_domains = {int(pid): (domain or "") for pid, domain in portal_rows}

    requested_channel = (channel or "").strip().lower()
    portal_filter = (portal or "").strip().lower()
    effective_portal_id = portal_id
    if effective_portal_id is None and portal_filter.isdigit():
        try:
            effective_portal_id = int(portal_filter)
        except Exception:
            effective_portal_id = None
    items: list[dict[str, Any]] = []
    per_source = max(limit * 2, 200)

    if requested_channel in ("", "bitrix_http"):
        q = select(BitrixHttpLog).where(BitrixHttpLog.status_code >= 400)
        if effective_portal_id is not None:
            q = q.where(BitrixHttpLog.portal_id == effective_portal_id)
        if trace_id:
            q = q.where(BitrixHttpLog.trace_id == trace_id)
        q = q.order_by(desc(BitrixHttpLog.created_at)).limit(per_source)
        rows = db.execute(q).scalars().all()
        for r in rows:
            summary = _safe_json(r.summary_json)
            err_code = (
                summary.get("bitrix_error_code")
                or summary.get("error_code")
                or (f"http_{r.status_code}" if r.status_code else "http_error")
            )
            err_msg = (
                summary.get("bitrix_error_desc")
                or summary.get("error_description_safe")
                or summary.get("safe_err")
                or ""
            )
            items.append(
                {
                    "id": f"bitrix_http:{r.id}",
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "portal_id": r.portal_id,
                    "portal_domain": portal_domains.get(int(r.portal_id or 0), "") if r.portal_id else "",
                    "trace_id": r.trace_id,
                    "channel": "bitrix_http",
                    "endpoint": r.path or "",
                    "method": r.method or "",
                    "code": str(err_code),
                    "message": str(err_msg),
                    "status_code": r.status_code,
                    "kind": r.kind or "",
                }
            )

    if requested_channel in ("", "inbound"):
        q = select(BitrixInboundEvent).where(
            BitrixInboundEvent.status_hint.isnot(None),
            BitrixInboundEvent.status_hint != "ok",
        )
        if effective_portal_id is not None:
            q = q.where(BitrixInboundEvent.portal_id == effective_portal_id)
        if trace_id:
            q = q.where(BitrixInboundEvent.trace_id == trace_id)
        q = q.order_by(desc(BitrixInboundEvent.created_at)).limit(per_source)
        rows = db.execute(q).scalars().all()
        for r in rows:
            hints = _safe_json(r.hints_json)
            err_code = (r.status_hint or hints.get("error_code") or "inbound_error")
            err_msg = hints.get("error") or hints.get("reason") or ""
            items.append(
                {
                    "id": f"inbound:{r.id}",
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "portal_id": r.portal_id,
                    "portal_domain": portal_domains.get(int(r.portal_id or 0), "") if r.portal_id else "",
                    "trace_id": r.trace_id,
                    "channel": "inbound",
                    "endpoint": r.path or "",
                    "method": r.method or "",
                    "code": str(err_code),
                    "message": str(err_msg),
                    "status_code": None,
                    "kind": r.event_name or "",
                }
            )

    if requested_channel in ("", "outbox"):
        q = select(Outbox).where(Outbox.status == "error")
        if effective_portal_id is not None:
            q = q.where(Outbox.portal_id == effective_portal_id)
        q = q.order_by(desc(Outbox.created_at)).limit(per_source)
        rows = db.execute(q).scalars().all()
        for r in rows:
            payload = _safe_json(r.payload_json)
            row_trace = payload.get("trace_id")
            if trace_id and row_trace != trace_id:
                continue
            code_guess = "outbox_error"
            msg = (r.error_message or "").strip()
            if "403" in msg:
                code_guess = "http_403"
            elif "401" in msg:
                code_guess = "http_401"
            elif "timeout" in msg.lower():
                code_guess = "timeout"
            items.append(
                {
                    "id": f"outbox:{r.id}",
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "portal_id": r.portal_id,
                    "portal_domain": portal_domains.get(int(r.portal_id or 0), "") if r.portal_id else "",
                    "trace_id": row_trace,
                    "channel": "outbox",
                    "endpoint": payload.get("method") or "",
                    "method": "POST",
                    "code": code_guess,
                    "message": msg[:500],
                    "status_code": None,
                    "kind": payload.get("kind") or "",
                }
            )

    code_filter = (code or "").strip().lower()
    if code_filter:
        items = [it for it in items if code_filter in str(it.get("code") or "").lower()]
    if portal_filter and not portal_filter.isdigit():
        items = [
            it for it in items
            if portal_filter in str(it.get("portal_domain") or "").lower()
        ]

    def _created(item: dict[str, Any]) -> float:
        raw = item.get("created_at")
        if not raw:
            return 0.0
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            return 0.0

    items.sort(key=_created, reverse=True)
    return items[:limit]


@router.get("/errors/export.json")
def export_errors_json(
    db: Session = Depends(get_db),
    limit: int = Query(500, ge=1, le=5000),
    portal_id: int | None = Query(None),
    portal: str | None = Query(None),
    trace_id: str | None = Query(None),
    channel: str | None = Query(None),
    code: str | None = Query(None),
):
    items = _collect_errors(
        db=db,
        limit=limit,
        portal_id=portal_id,
        portal=portal,
        trace_id=trace_id,
        channel=channel,
        code=code,
    )
    return JSONResponse({"items": items, "total": len(items)})


@router.get("/errors/export.csv")
def export_errors_csv(
    db: Session = Depends(get_db),
    limit: int = Query(500, ge=1, le=5000),
    portal_id: int | None = Query(None),
    portal: str | None = Query(None),
    trace_id: str | None = Query(None),
    channel: str | None = Query(None),
    code: str | None = Query(None),
):
    items = _collect_errors(
        db=db,
        limit=limit,
        portal_id=portal_id,
        portal=portal,
        trace_id=trace_id,
        channel=channel,
        code=code,
    )
    cols = [
        "created_at",
        "channel",
        "portal_id",
        "portal_domain",
        "trace_id",
        "method",
        "endpoint",
        "code",
        "status_code",
        "kind",
        "message",
    ]
    lines = [",".join(cols)]
    for it in items:
        row: list[str] = []
        for c in cols:
            v = str(it.get(c, "") or "")
            v = v.replace('"', '""')
            if "," in v or "\n" in v or '"' in v:
                v = f"\"{v}\""
            row.append(v)
        lines.append(",".join(row))
    body = "\n".join(lines)
    headers = {"Content-Disposition": "attachment; filename=api_errors.csv"}
    return PlainTextResponse(body, media_type="text/csv; charset=utf-8", headers=headers)
