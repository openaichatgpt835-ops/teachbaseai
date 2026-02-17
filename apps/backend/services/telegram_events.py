"""Telegram inbound events."""
from __future__ import annotations

import json
import logging
import uuid
import os

from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.backend.models.dialog import Dialog, Message
from apps.backend.models.event import Event
from apps.backend.models.outbox import Outbox
from apps.backend.models.portal import PortalUsersAccess
from apps.backend.models.kb import KBFile, KBJob
from apps.backend.services.kb_rag import answer_from_kb
from apps.backend.services.bot_flow_engine import execute_client_flow
from apps.backend.services.billing import (
    is_limit_exceeded,
    get_pricing,
    calc_cost_rub,
    record_usage,
)
from apps.backend.services.telegram_settings import (
    normalize_telegram_username,
    get_portal_telegram_settings,
    get_portal_telegram_token_plain,
)
from apps.backend.services.kb_storage import ensure_portal_dir
from apps.backend.clients.telegram import telegram_get_file, telegram_download_file
from apps.backend.config import get_settings

logger = logging.getLogger(__name__)

MSG_MISSING_USERNAME = "Укажите username в Telegram и напишите боту снова."
MSG_NO_ACCESS = "Нет доступа. Обратитесь к администратору портала."
MSG_UPLOADS_DISABLED = "Загрузка файлов отключена в настройках."
MSG_FILE_RECEIVED = "Файл получил, изучаю 🔍"
MSG_FILE_QUEUED = "Файл получен и отправлен на индексацию."
MSG_LIMIT_EXCEEDED = "Лимит запросов исчерпан. Обратитесь к администратору портала."
MSG_KB_EMPTY = "База знаний пока пуста. Обратитесь к администратору портала."
MSG_SERVICE_DOWN = "Сервис ответа временно недоступен. Попробуйте позже."


def _dialog_id(chat_id: int | str) -> str:
    return f"tg:{chat_id}"


def _find_allowed_user(db: Session, portal_id: int, username: str | None) -> PortalUsersAccess | None:
    if not username:
        return None
    uname = normalize_telegram_username(username)
    if not uname:
        return None
    return db.execute(
        select(PortalUsersAccess)
        .where(
            PortalUsersAccess.portal_id == portal_id,
            PortalUsersAccess.telegram_username == uname,
        )
    ).scalar_one_or_none()


def process_telegram_update(
    db: Session,
    portal_id: int,
    kind: str,
    update: dict,
) -> dict:
    message = update.get("message") or update.get("edited_message")
    if not isinstance(message, dict):
        return {"status": "ignored"}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    chat_type = (chat.get("type") or "").lower()
    if not chat_id:
        return {"status": "ignored", "reason": "no_chat_id"}
    if chat_type and chat_type != "private":
        return {"status": "ignored", "reason": "chat_not_private"}
    text = str(message.get("text") or "").strip()
    has_media = any(
        message.get(k)
        for k in ("document", "audio", "voice", "video", "video_note")
    )
    if not text and not has_media:
        return {"status": "ignored", "reason": "no_text"}
    update_id = update.get("update_id")
    message_id = message.get("message_id")
    sender = message.get("from") or {}
    sender_username = sender.get("username")
    sender_user_id = None

    access_row = None
    if kind == "staff":
        if not sender_username:
            provider_event_id = str(update_id or message_id or uuid.uuid4())
            db.add(Event(
                portal_id=portal_id,
                provider_event_id=provider_event_id + "_blocked",
                event_type="blocked_by_acl",
                payload_json=json.dumps({
                    "chat_id": chat_id,
                    "username": sender_username,
                    "kind": kind,
                    "reason": "missing_username",
                }, ensure_ascii=False),
            ))
            db.commit()
            return {
                "status": "blocked",
                "reason": "acl",
                "detail": "missing_username",
                "reply": MSG_MISSING_USERNAME,
                "chat_id": chat_id,
            }
        access_row = _find_allowed_user(db, portal_id, sender_username)
        if not access_row:
            provider_event_id = str(update_id or message_id or uuid.uuid4())
            db.add(Event(
                portal_id=portal_id,
                provider_event_id=provider_event_id + "_blocked",
                event_type="blocked_by_acl",
                payload_json=json.dumps({
                    "chat_id": chat_id,
                    "username": sender_username,
                    "kind": kind,
                    "reason": "not_in_allowlist",
                }, ensure_ascii=False),
            ))
            db.commit()
            return {
                "status": "blocked",
                "reason": "acl",
                "detail": "no_access",
                "reply": MSG_NO_ACCESS,
                "chat_id": chat_id,
            }
        sender_user_id = access_row.user_id

    if has_media:
        settings = get_portal_telegram_settings(db, portal_id)
        allow_uploads = bool(settings.get(kind, {}).get("allow_uploads"))
        if not allow_uploads:
            return {
                "status": "blocked",
                "reason": "uploads_disabled",
                "reply": MSG_UPLOADS_DISABLED,
                "chat_id": chat_id,
            }
        token = get_portal_telegram_token_plain(db, portal_id, kind) or ""
        if not token:
            return {"status": "error", "reason": "missing_bot_token", "chat_id": chat_id}
        doc = message.get("document") or message.get("audio") or message.get("voice") or message.get("video") or message.get("video_note")
        file_id = doc.get("file_id") if isinstance(doc, dict) else None
        file_name = doc.get("file_name") if isinstance(doc, dict) else None
        mime_type = doc.get("mime_type") if isinstance(doc, dict) else None
        if not file_name:
            ext = ".ogg" if message.get("voice") or message.get("video_note") else ""
            file_name = f"tg_{message_id or update_id or 'file'}{ext}"
        if not file_id:
            return {"status": "ignored", "reason": "no_file_id"}
        info, err = telegram_get_file(token, file_id)
        if not info or err:
            return {"status": "error", "reason": "file_info_failed", "detail": err, "chat_id": chat_id}
        file_path = info.get("file_path")
        if not file_path:
            return {"status": "error", "reason": "file_path_missing", "chat_id": chat_id}
        portal_dir = ensure_portal_dir(portal_id)
        safe_name = os.path.basename(file_name)
        suffix = uuid.uuid4().hex[:8]
        dst_path = os.path.join(portal_dir, f"{suffix}_{safe_name}")
        ok, derr = telegram_download_file(token, file_path, dst_path)
        if not ok:
            return {"status": "error", "reason": "download_failed", "detail": derr, "chat_id": chat_id}
        size = os.path.getsize(dst_path) if os.path.exists(dst_path) else None
        aud = "client" if kind == "client" else "staff"
        rec = KBFile(
            portal_id=portal_id,
            filename=safe_name,
            audience=aud,
            mime_type=mime_type,
            size_bytes=size or 0,
            storage_path=dst_path,
            sha256="",
            status="uploaded",
            uploaded_by_type="telegram",
            uploaded_by_id=str(chat_id),
            uploaded_by_name=sender_username or (access_row.display_name if access_row else None),
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        job = KBJob(
            portal_id=rec.portal_id,
            job_type="ingest",
            status="queued",
            payload_json={
                "file_id": rec.id,
                "tg_chat_id": chat_id,
                "tg_kind": kind,
                "tg_filename": safe_name,
            },
        )
        db.add(job)
        rec.status = "queued"
        db.add(rec)
        db.commit()
        outbox = Outbox(
            portal_id=portal_id,
            message_id=None,
            status="created",
            payload_json=json.dumps({
                "provider": "telegram",
                "kind": kind,
                "chat_id": chat_id,
                "body": MSG_FILE_RECEIVED,
            }, ensure_ascii=False),
        )
        db.add(outbox)
        db.commit()
        try:
            from redis import Redis
            from rq import Queue
            s = get_settings()
            r = Redis(host=s.redis_host, port=s.redis_port)
            q = Queue(s.rq_ingest_queue_name or "ingest", connection=r)
            q.enqueue(
                "apps.worker.jobs.process_kb_job",
                job.id,
                job_timeout=max(300, int(s.kb_job_timeout_seconds or 3600)),
            )
            q_outbox = Queue(s.rq_outbox_queue_name or "outbox", connection=r)
            q_outbox.enqueue("apps.worker.jobs.process_outbox", outbox.id)
        except Exception as e:
            logger.exception("telegram enqueue failed: %s", e)
            job.error_message = f"enqueue_failed:{str(e)[:180]}"
            db.commit()
        return {
            "status": "ok",
            "reply": MSG_FILE_QUEUED,
            "chat_id": chat_id,
        }

    provider_event_id = str(update_id or message_id or uuid.uuid4())
    db.add(Event(
        portal_id=portal_id,
        provider_event_id=provider_event_id,
        event_type="rx",
        payload_json=json.dumps({
            "chat_id": chat_id,
            "text": text,
            "username": sender_username,
            "kind": kind,
        }, ensure_ascii=False),
    ))
    db.commit()

    dialog_key = _dialog_id(chat_id)
    dialog = db.execute(
        select(Dialog).where(Dialog.portal_id == portal_id, Dialog.provider_dialog_id == dialog_key)
    ).scalar_one_or_none()
    if not dialog:
        dialog = Dialog(
            portal_id=portal_id,
            provider_dialog_id=dialog_key,
            provider_dialog_id_raw=str(chat_id),
        )
        db.add(dialog)
        db.commit()
        db.refresh(dialog)

    msg = Message(
        dialog_id=dialog.id,
        provider_message_id=str(message_id or update_id or ""),
        direction="rx",
        body=text,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    response_body = None
    if text.lower() == "ping":
        response_body = "pong"
    else:
        if is_limit_exceeded(db, portal_id):
            record_usage(
                db,
                portal_id=portal_id,
                user_id=str(sender_user_id) if sender_user_id else None,
                request_id=str(provider_event_id),
                kind="chat",
                model=None,
                tokens_prompt=None,
                tokens_completion=None,
                tokens_total=None,
                cost_rub=None,
                status="blocked",
                error_code="limit_exceeded",
            )
            response_body = MSG_LIMIT_EXCEEDED
        else:
            if kind == "client":
                try:
                    response_body = execute_client_flow(db, portal_id, dialog.id, text)
                    rag_answer = response_body
                    rag_err = None
                    usage = None
                except Exception as e:
                    logger.exception("client flow failed: %s", e)
                    rag_answer, rag_err, usage = answer_from_kb(
                        db,
                        portal_id,
                        text,
                        dialog_id=dialog.id,
                        audience="client",
                    )
            else:
                rag_answer, rag_err, usage = answer_from_kb(
                    db,
                    portal_id,
                    text,
                    dialog_id=dialog.id,
                    audience="staff",
                )
            if rag_answer:
                response_body = rag_answer
            elif rag_err == "kb_empty":
                response_body = MSG_KB_EMPTY
            else:
                logger.warning("kb_rag_error portal_id=%s err=%s", portal_id, rag_err)
                response_body = MSG_SERVICE_DOWN
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
                portal_id=portal_id,
                user_id=str(sender_user_id) if sender_user_id else None,
                request_id=str(provider_event_id),
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
        provider_message_id=f"{provider_event_id}_tx",
        direction="tx",
        body=response_body,
    )
    db.add(msg_tx)
    db.commit()
    db.refresh(msg_tx)

    trace_id = str(uuid.uuid4())[:16]
    outbox = Outbox(
        portal_id=portal_id,
        message_id=msg_tx.id,
        status="created",
        payload_json=json.dumps({
            "provider": "telegram",
            "kind": kind,
            "chat_id": chat_id,
            "body": response_body,
            "trace_id": trace_id,
        }),
    )
    db.add(outbox)
    db.commit()
    try:
        from redis import Redis
        from rq import Queue
        s = get_settings()
        r = Redis(host=s.redis_host, port=s.redis_port)
        q = Queue(s.rq_outbox_queue_name or "outbox", connection=r)
        q.enqueue("apps.worker.jobs.process_outbox", outbox.id)
    except Exception as e:
        logger.exception("telegram enqueue failed: %s", e)
        outbox.status = "error"
        outbox.error_message = str(e)[:200]
        db.commit()
    return {"status": "ok", "dialog_id": dialog.id, "outbox_id": outbox.id}
