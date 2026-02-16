"""Обработка входящих событий Bitrix."""
import json
import logging
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.backend.models.portal import Portal, PortalToken, PortalUsersAccess
from apps.backend.models.dialog import Dialog, Message
from apps.backend.models.event import Event
from apps.backend.models.outbox import Outbox
from apps.backend.services.kb_rag import answer_from_kb
from apps.backend.services.billing import (
    is_limit_exceeded,
    get_pricing,
    calc_cost_rub,
    record_usage,
)

logger = logging.getLogger(__name__)


def _get_portal_by_domain(db: Session, domain: str) -> Portal | None:
    d = domain.replace("https://", "").replace("http://", "").split(".")[0]
    return db.execute(select(Portal).where(Portal.domain.ilike(f"%{d}%"))).scalar_one_or_none()


def _get_portal_by_member(db: Session, member_id: str) -> Portal | None:
    return db.execute(select(Portal).where(Portal.member_id == member_id)).scalar_one_or_none()


def _get_portal_by_app_token(db: Session, application_token: str) -> Portal | None:
    return db.execute(select(Portal).where(Portal.application_token == application_token)).scalar_one_or_none()


def _ensure_portal(db: Session, domain: str, member_id: str | None) -> Portal:
    domain_clean = domain.replace("https://", "").replace("http://", "").rstrip("/")
    p = db.execute(select(Portal).where(Portal.domain == domain_clean)).scalar_one_or_none()
    if p:
        if member_id and not p.member_id:
            p.member_id = member_id
            db.commit()
        return p
    p = Portal(domain=domain_clean, member_id=member_id or "", status="active")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _dedup_event(db: Session, portal_id: int, provider_event_id: str) -> bool:
    """True если событие уже обработано."""
    e = db.execute(
        select(Event).where(
            Event.portal_id == portal_id,
            Event.provider_event_id == provider_event_id,
        )
    ).scalar_one_or_none()
    return e is not None


def process_imbot_message(db: Session, data: dict, auth: dict) -> dict:
    """Обработка ONIMBOTMESSAGEADD."""
    bots = data.get("BOT") or []
    params = data.get("PARAMS") or {}
    dialog_id = str(params.get("DIALOG_ID", ""))
    message_id = str(params.get("MESSAGE_ID", ""))
    body = str(params.get("MESSAGE", ""))
    domain = ""
    member_id = ""
    app_token = ""
    access_token = ""
    bot_id = 0
    b = None
    bot_id_hint = None
    if isinstance(bots, list) and bots:
        if isinstance(bots[0], dict):
            b = bots[0]
    elif isinstance(bots, dict):
        for k, v in bots.items():
            if isinstance(v, dict):
                b = v
                bot_id_hint = k
                break
    if b:
        auth_data = b.get("AUTH") or {}
        domain = auth_data.get("domain", "") or b.get("domain", "") or b.get("DOMAIN", "")
        member_id = auth_data.get("member_id", "") or b.get("member_id", "") or b.get("MEMBER_ID", "")
        app_token = auth_data.get("application_token", "") or b.get("application_token", "") or b.get("APP_SID", "")
        access_token = auth_data.get("access_token", "") or b.get("access_token", "") or b.get("ACCESS_TOKEN", "")
        bot_access = b.get("access_token") or b.get("ACCESS_TOKEN")
        if not app_token and bot_access:
            app_token = str(bot_access)
        bot_id_val = b.get("BOT_ID") or b.get("bot_id")
        if bot_id_val is None and bot_id_hint is not None:
            bot_id_val = bot_id_hint
        try:
            bot_id = int(bot_id_val or 0)
        except (TypeError, ValueError):
            bot_id = 0
    if not domain:
        domain = auth.get("domain", "") or auth.get("DOMAIN", "")
    if not app_token:
        app_token = auth.get("application_token", "") or auth.get("APP_SID", "") or auth.get("APPLICATION_TOKEN", "")
    if not access_token:
        access_token = auth.get("access_token", "") or auth.get("ACCESS_TOKEN", "") or auth.get("AUTH_ID", "")
    if not member_id:
        member_id = auth.get("member_id", "") or auth.get("MEMBER_ID", "")
    portal = None
    if member_id:
        portal = _get_portal_by_member(db, member_id)
        if portal and not domain:
            domain = portal.domain
    if not portal and app_token:
        portal = _get_portal_by_app_token(db, app_token)
        if portal and not domain:
            domain = portal.domain
    if not domain:
        return {"error": "no domain"}
    if not portal:
        portal = _ensure_portal(db, domain, member_id)
    if _dedup_event(db, portal.id, message_id):
        return {"status": "duplicate"}
    event = Event(
        portal_id=portal.id,
        provider_event_id=message_id,
        event_type="rx",
        payload_json=json.dumps(params),
    )
    db.add(event)
    db.commit()
    # ACL: allowlist (portal_users_access). Block messages from users not in allowlist.
    sender_user_id = str(
        params.get("USER_ID")
        or params.get("FROM_USER_ID")
        or params.get("AUTHOR_ID")
        or ""
    )
    if not sender_user_id and dialog_id.startswith("user"):
        try:
            sender_user_id = dialog_id.replace("user", "").strip()
        except Exception:
            pass
    dialog_id_norm = dialog_id
    if not dialog_id_norm and sender_user_id:
        dialog_id_norm = sender_user_id
    if dialog_id_norm.startswith("user"):
        dialog_id_norm = dialog_id_norm.replace("user", "").strip()
    dialog = db.execute(
        select(Dialog).where(
            Dialog.portal_id == portal.id,
            Dialog.provider_dialog_id == dialog_id_norm,
        )
    ).scalar_one_or_none()
    if not dialog:
        dialog = Dialog(
            portal_id=portal.id,
            provider_dialog_id=dialog_id_norm,
            provider_dialog_id_raw=dialog_id,
        )
        db.add(dialog)
        db.commit()
        db.refresh(dialog)

    allowed = set(
        r.user_id for r in db.execute(
            select(PortalUsersAccess).where(PortalUsersAccess.portal_id == portal.id)
        ).scalars().all()
    )
    if allowed and (not sender_user_id or sender_user_id not in allowed):
        db.add(Event(
            portal_id=portal.id,
            provider_event_id=message_id + "_blocked",
            event_type="blocked_by_acl",
            payload_json=json.dumps({
                "sender_user_id": sender_user_id,
                "dialog_id": dialog_id_norm,
                "reason": "unknown_user" if not sender_user_id else "not_in_allowlist",
            }),
        ))
        db.commit()
        return {"status": "blocked", "reason": "acl", "detail": "Нет доступа. Обратитесь к администратору портала."}
    msg = Message(
        dialog_id=dialog.id,
        provider_message_id=message_id,
        direction="rx",
        body=body,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    response_body = None
    sender_uid = sender_user_id or None
    if body.strip().lower() == "ping":
        response_body = "pong"
    else:
        if is_limit_exceeded(db, portal.id):
            record_usage(
                db,
                portal_id=portal.id,
                user_id=sender_uid,
                request_id=message_id,
                kind="chat",
                model=None,
                tokens_prompt=None,
                tokens_completion=None,
                tokens_total=None,
                cost_rub=None,
                status="blocked",
                error_code="limit_exceeded",
            )
            response_body = "Лимит запросов по порталу исчерпан. Обратитесь к администратору."
        else:
            rag_answer, rag_err, usage = answer_from_kb(db, portal.id, body, dialog_id=dialog.id)
            if rag_answer:
                response_body = rag_answer
            elif rag_err == "kb_empty":
                response_body = "База знаний пока пуста. Обратитесь к администратору портала."
            else:
                logger.warning("kb_rag_error portal_id=%s err=%s", portal.id, rag_err)
                response_body = "Сервис ответа недоступен (код: %s). Попробуйте позже." % (rag_err or "error")
            pricing = get_pricing(db)
            tokens_prompt = None
            tokens_completion = None
            tokens_total = None
            model_name = None
            if isinstance(usage, dict):
                tokens_prompt = usage.get("prompt_tokens")
                tokens_completion = usage.get("completion_tokens")
                tokens_total = usage.get("total_tokens")
                model_name = usage.get("model")
            cost = calc_cost_rub(int(tokens_total) if tokens_total else None, pricing.get("chat_rub_per_1k", 0.0))
            record_usage(
                db,
                portal_id=portal.id,
                user_id=sender_uid,
                request_id=message_id,
                kind="chat",
                model=model_name,
                tokens_prompt=int(tokens_prompt) if tokens_prompt else None,
                tokens_completion=int(tokens_completion) if tokens_completion else None,
                tokens_total=int(tokens_total) if tokens_total else None,
                cost_rub=cost,
                status="ok" if rag_answer else "error",
                error_code=None if rag_answer else (rag_err or "error"),
            )
    msg_tx = Message(
        dialog_id=dialog.id,
        provider_message_id=f"{message_id}_tx",
        direction="tx",
        body=response_body,
    )
    db.add(msg_tx)
    db.commit()
    db.refresh(msg_tx)
    import uuid
    trace_id = str(uuid.uuid4())[:16]
    outbox = Outbox(
        portal_id=portal.id,
        message_id=msg_tx.id,
        status="created",
        payload_json=json.dumps({
            "dialog_id": dialog_id_norm,
            "sender_user_id": sender_user_id,
            "body": response_body,
            "access_token": access_token,
            "app_token": app_token,
            "domain": domain,
            "bot_id": bot_id,
            "trace_id": trace_id,
        }),
    )
    db.add(outbox)
    db.commit()
    try:
        from redis import Redis
        from rq import Queue
        from apps.backend.config import get_settings
        s = get_settings()
        r = Redis(host=s.redis_host, port=s.redis_port)
        q = Queue("default", connection=r)
        q.enqueue("apps.worker.jobs.process_outbox", outbox.id)
    except Exception as e:
        logger.exception("Enqueue failed: %s", e)
        outbox.status = "error"
        outbox.error_message = str(e)
        db.commit()
    return {"status": "ok", "dialog_id": dialog.id}
