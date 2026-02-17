import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.backend.auth import require_portal_access
from apps.backend.deps import get_db
from apps.backend.models.bitrix_inbound_event import BitrixInboundEvent
from apps.backend.models.dialog import Dialog, Message
from apps.backend.models.topic_summary import PortalTopicSummary
from apps.backend.services.billing import get_portal_usage_summary
from apps.backend.services.gigachat_client import DEFAULT_API_BASE, chat_complete
from apps.backend.utils.api_errors import error_envelope
from apps.backend.services.kb_settings import (
    get_effective_gigachat_settings,
    get_valid_gigachat_access_token,
)

router = APIRouter()


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


@router.get("/portals/{portal_id}/dialogs/recent")
async def get_recent_dialog_messages(
    portal_id: int,
    request: Request,
    limit: int = 30,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    """Recent dialog messages for portal (rx/tx) for iframe status page."""
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    if limit < 1:
        limit = 1
    if limit > 100:
        limit = 100
    q = (
        select(Message, Dialog)
        .join(Dialog, Dialog.id == Message.dialog_id)
        .where(Dialog.portal_id == portal_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    rows = db.execute(q).all()
    items = []
    for msg, dialog in rows:
        body = (msg.body or "")
        if len(body) > 200:
            body = body[:200] + "…"
        items.append({
            "dialog_id": dialog.provider_dialog_id,
            "direction": msg.direction,
            "body": body,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        })
    return JSONResponse({"items": items, "count": len(items)})


@router.get("/portals/{portal_id}/dialogs/summary")
async def get_dialogs_summary(
    portal_id: int,
    request: Request,
    limit: int = 120,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    """Semantic 3-topic summary for recent portal dialogs (iframe analytics widget)."""
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    if limit < 10:
        limit = 10
    if limit > 300:
        limit = 300

    today = datetime.utcnow().date()
    latest = (
        db.query(PortalTopicSummary)
        .filter(PortalTopicSummary.portal_id == portal_id)
        .filter(PortalTopicSummary.day == today)
        .order_by(PortalTopicSummary.created_at.desc())
        .first()
    )
    if latest:
        return JSONResponse(
            {
                "items": latest.items or [],
                "day": latest.day.isoformat(),
                "count": len(latest.items or []),
                "stale": False,
            }
        )

    day_start = datetime.combine(today, datetime.min.time())
    day_end = day_start + timedelta(days=1)
    q = (
        select(Message.body)
        .join(Dialog, Dialog.id == Message.dialog_id)
        .where(Dialog.portal_id == portal_id)
        .where(Message.direction == "rx")
        .where(Message.body.isnot(None))
        .where(Message.created_at >= day_start)
        .where(Message.created_at < day_end)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    rows = db.execute(q).scalars().all()
    texts = [str(t).strip() for t in rows if t and str(t).strip()]

    source_from = day_start
    source_to = day_end
    if len(texts) < 10:
        week_start = datetime.utcnow() - timedelta(days=7)
        q = (
            select(Message.body)
            .join(Dialog, Dialog.id == Message.dialog_id)
            .where(Dialog.portal_id == portal_id)
            .where(Message.direction == "rx")
            .where(Message.body.isnot(None))
            .where(Message.created_at >= week_start)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        rows = db.execute(q).scalars().all()
        texts = [str(t).strip() for t in rows if t and str(t).strip()]
        source_from = week_start
        source_to = datetime.utcnow()

    if len(texts) < 8:
        last = (
            db.query(PortalTopicSummary)
            .filter(PortalTopicSummary.portal_id == portal_id)
            .order_by(PortalTopicSummary.day.desc())
            .first()
        )
        if last:
            return JSONResponse(
                {
                    "items": last.items or [],
                    "day": last.day.isoformat(),
                    "count": len(last.items or []),
                    "stale": True,
                }
            )
        return JSONResponse({"items": [], "count": len(texts)}, status_code=200)

    settings = get_effective_gigachat_settings(db, portal_id)
    token, err = get_valid_gigachat_access_token(db)
    if err:
        return _err(request, "gigachat_unavailable", "gigachat_unavailable", 503)

    sample = "\n".join(texts[:160])
    system = (
        "Ты аналитик запросов. На входе список пользовательских сообщений. "
        "Сгруппируй по смыслу в 3 главные темы. Для каждой темы верни одно "
        "осмысленное предложение на русском и оценку частоты (score) от 1 до 100 "
        "по относительной популярности. Формат строго JSON массив из 3 объектов "
        "с полями: topic, score."
    )
    user = (
        "Сообщения:\n" + sample + "\n\n"
        "Верни JSON массив из 3 объектов. Никакого текста вокруг JSON."
    )
    content, err2, _usage = chat_complete(
        settings.get("api_base") or DEFAULT_API_BASE,
        token,
        settings.get("chat_model") or "GigaChat-2-Pro",
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        max_tokens=260,
    )
    items: list[dict] = []
    if not err2 and content:
        try:
            data = json.loads(str(content).strip())
            if isinstance(data, list):
                for it in data:
                    topic = str(it.get("topic", "")).strip()
                    score = it.get("score")
                    if topic:
                        try:
                            score_int = int(score)
                        except Exception:
                            score_int = None
                        items.append({"topic": topic, "score": score_int})
        except Exception:
            items = []

    if len(items) >= 3:
        rec = PortalTopicSummary(
            portal_id=portal_id,
            day=today,
            source_from=source_from,
            source_to=source_to,
            items=items,
        )
        db.add(rec)
        db.commit()
        return JSONResponse(
            {
                "items": items,
                "day": today.isoformat(),
                "count": len(items),
                "stale": False,
            }
        )

    last = (
        db.query(PortalTopicSummary)
        .filter(PortalTopicSummary.portal_id == portal_id)
        .order_by(PortalTopicSummary.day.desc())
        .first()
    )
    if last:
        return JSONResponse(
            {
                "items": last.items or [],
                "day": last.day.isoformat(),
                "count": len(last.items or []),
                "stale": True,
            }
        )
    return JSONResponse({"items": [], "error": "summary_failed"}, status_code=200)


@router.get("/portals/{portal_id}/users/stats")
async def get_portal_user_stats(
    portal_id: int,
    request: Request,
    hours: int = 24,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    if hours < 1:
        hours = 1
    if hours > 168:
        hours = 168
    since = datetime.utcnow() - timedelta(hours=hours)
    q = (
        db.query(BitrixInboundEvent.user_id, func.count(BitrixInboundEvent.id))
        .filter(BitrixInboundEvent.portal_id == portal_id)
        .filter(BitrixInboundEvent.event_name == "ONIMBOTMESSAGEADD")
        .filter(BitrixInboundEvent.created_at >= since)
        .group_by(BitrixInboundEvent.user_id)
    )
    stats = {str(uid): int(cnt) for uid, cnt in q.all() if uid is not None}
    return JSONResponse({"hours": hours, "stats": stats})


@router.get("/portals/{portal_id}/billing/summary")
async def get_portal_billing_summary(
    portal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    pid: int = Depends(require_portal_access),
):
    if pid != portal_id:
        return _err(request, "forbidden", "Forbidden", 403)
    return JSONResponse(get_portal_usage_summary(db, portal_id))
