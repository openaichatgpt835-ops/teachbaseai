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
from apps.backend.models.kb import KBFile, KBJob, KBFileAccess, KBFolderAccess
from apps.backend.models.portal import Portal
from apps.backend.models.account import AccountMembership, AppUserIdentity, AccountUserGroupMember
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
from apps.backend.services.kb_acl import default_kb_access_for_role, kb_acl_principals_for_membership, resolve_kb_acl_access
from apps.backend.clients.telegram import telegram_get_file, telegram_download_file
from apps.backend.config import get_settings

logger = logging.getLogger(__name__)

MSG_MISSING_USERNAME = (
    "\u0423\u043a\u0430\u0436\u0438\u0442\u0435 username \u0432 Telegram \u0438 "
    "\u043d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 \u0431\u043e\u0442\u0443 \u0441\u043d\u043e\u0432\u0430."
)
MSG_NO_ACCESS = (
    "\u041d\u0435\u0442 \u0434\u043e\u0441\u0442\u0443\u043f\u0430. "
    "\u041e\u0431\u0440\u0430\u0442\u0438\u0442\u0435\u0441\u044c \u043a "
    "\u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u0443 \u043f\u043e\u0440\u0442\u0430\u043b\u0430."
)
MSG_UPLOADS_DISABLED = (
    "\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430 \u0444\u0430\u0439\u043b\u043e\u0432 "
    "\u043e\u0442\u043a\u043b\u044e\u0447\u0435\u043d\u0430 \u0432 \u043d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0430\u0445."
)
MSG_FILE_RECEIVED = (
    "\u0424\u0430\u0439\u043b \u043f\u043e\u043b\u0443\u0447\u0438\u043b, "
    "\u0438\u0437\u0443\u0447\u0430\u044e \u0435\u0433\u043e."
)
MSG_FILE_QUEUED = (
    "\u0424\u0430\u0439\u043b \u043f\u043e\u043b\u0443\u0447\u0435\u043d \u0438 "
    "\u043e\u0442\u043f\u0440\u0430\u0432\u043b\u0435\u043d \u043d\u0430 \u0438\u043d\u0434\u0435\u043a\u0441\u0430\u0446\u0438\u044e."
)
MSG_LIMIT_EXCEEDED = (
    "\u041b\u0438\u043c\u0438\u0442 \u0437\u0430\u043f\u0440\u043e\u0441\u043e\u0432 "
    "\u0438\u0441\u0447\u0435\u0440\u043f\u0430\u043d. \u041e\u0431\u0440\u0430\u0442\u0438\u0442\u0435\u0441\u044c \u043a "
    "\u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u0443 \u043f\u043e\u0440\u0442\u0430\u043b\u0430."
)
MSG_KB_EMPTY = (
    "\u0411\u0430\u0437\u0430 \u0437\u043d\u0430\u043d\u0438\u0439 \u043f\u043e\u043a\u0430 "
    "\u043f\u0443\u0441\u0442\u0430. \u041e\u0431\u0440\u0430\u0442\u0438\u0442\u0435\u0441\u044c \u043a "
    "\u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u0443 \u043f\u043e\u0440\u0442\u0430\u043b\u0430."
)
MSG_SERVICE_DOWN = (
    "\u0421\u0435\u0440\u0432\u0438\u0441 \u043e\u0442\u0432\u0435\u0442\u0430 "
    "\u0432\u0440\u0435\u043c\u0435\u043d\u043d\u043e \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d. "
    "\u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u043f\u043e\u0437\u0436\u0435."
)
MSG_NO_CLIENT_MATERIALS = (
    "\u0414\u043b\u044f \u0432\u0430\u0441 \u043f\u043e\u043a\u0430 \u043d\u0435\u0442 "
    "\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0445 \u043c\u0430\u0442\u0435\u0440\u0438\u0430\u043b\u043e\u0432."
)


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


def _account_scope_portal_ids(db: Session, portal_id: int) -> list[int]:
    portal = db.get(Portal, int(portal_id))
    if not portal or not portal.account_id:
        return [int(portal_id)]
    rows = db.execute(
        select(Portal.id).where(Portal.account_id == int(portal.account_id)).order_by(Portal.id.asc())
    ).scalars().all()
    ids = [int(x) for x in rows if x is not None]
    return ids or [int(portal_id)]


def _telegram_client_acl_subject_ctx(db: Session, portal_id: int, username: str | None) -> dict[str, object] | None:
    uname = normalize_telegram_username(username)
    if not uname:
        return None
    portal = db.get(Portal, int(portal_id))
    if not portal or not portal.account_id:
        return None
    membership = db.execute(
        select(AccountMembership)
        .join(AppUserIdentity, AppUserIdentity.user_id == AccountMembership.user_id)
        .where(AccountMembership.account_id == int(portal.account_id))
        .where(AccountMembership.status == "active")
        .where(AppUserIdentity.provider == "telegram")
        .where(AppUserIdentity.integration_id.is_(None))
        .where(AppUserIdentity.external_id == uname)
        .order_by(AccountMembership.id.asc())
    ).scalar_one_or_none()
    if not membership:
        return None
    group_ids = db.execute(
        select(AccountUserGroupMember.group_id).where(AccountUserGroupMember.membership_id == int(membership.id))
    ).scalars().all()
    return {
        "membership_id": int(membership.id),
        "group_ids": [int(x) for x in group_ids if x is not None],
        "role": str(membership.role or "client"),
        "audience": "client",
    }


def _all_account_scope_file_ids(db: Session, *, portal_id: int, audience: str) -> set[int]:
    portal = db.get(Portal, int(portal_id))
    if portal and portal.account_id:
        rows = db.execute(
            select(KBFile.id)
            .where(
                ((KBFile.account_id == int(portal.account_id)) | ((KBFile.account_id.is_(None)) & (KBFile.portal_id.in_(_account_scope_portal_ids(db, portal_id)))))
            )
            .where(KBFile.audience == audience)
            .where(KBFile.status == "ready")
        ).scalars().all()
    else:
        rows = db.execute(
            select(KBFile.id)
            .where(KBFile.portal_id.in_(_account_scope_portal_ids(db, portal_id)))
            .where(KBFile.audience == audience)
            .where(KBFile.status == "ready")
        ).scalars().all()
    return {int(x) for x in rows if x is not None}


def _filter_file_ids_by_kb_acl(
    db: Session,
    *,
    file_ids: set[int],
    membership_id: int | None,
    group_ids: list[int] | None,
    role: str | None,
    audience: str | None,
) -> set[int]:
    if not file_ids:
        return set()
    rows = db.execute(select(KBFile.id, KBFile.folder_id).where(KBFile.id.in_(sorted(file_ids)))).all()
    folder_ids = sorted({int(folder_id) for _fid, folder_id in rows if folder_id is not None})
    file_acl_rows = db.execute(
        select(KBFileAccess.file_id, KBFileAccess.principal_type, KBFileAccess.principal_id, KBFileAccess.access_level)
        .where(KBFileAccess.file_id.in_(sorted(file_ids)))
    ).all()
    folder_acl_rows = []
    if folder_ids:
        folder_acl_rows = db.execute(
            select(KBFolderAccess.folder_id, KBFolderAccess.principal_type, KBFolderAccess.principal_id, KBFolderAccess.access_level)
            .where(KBFolderAccess.folder_id.in_(folder_ids))
        ).all()
    principals = kb_acl_principals_for_membership(membership_id, role, audience, group_ids)
    file_acl_map: dict[int, list[tuple[str, str, str]]] = {}
    for file_id, principal_type, principal_id, access_level in file_acl_rows:
        file_acl_map.setdefault(int(file_id), []).append((str(principal_type), str(principal_id), str(access_level)))
    folder_acl_map: dict[int, list[tuple[str, str, str]]] = {}
    for folder_id, principal_type, principal_id, access_level in folder_acl_rows:
        folder_acl_map.setdefault(int(folder_id), []).append((str(principal_type), str(principal_id), str(access_level)))
    allowed: set[int] = set()
    for file_id, folder_id in rows:
        inherited = default_kb_access_for_role(role)
        if folder_id is not None:
            inherited = resolve_kb_acl_access(folder_acl_map.get(int(folder_id), []), principals, inherited)
        effective = resolve_kb_acl_access(file_acl_map.get(int(file_id), []), principals, inherited)
        if effective in {"read", "write", "admin"}:
            allowed.add(int(file_id))
    return allowed


def _telegram_client_file_scope(db: Session, portal_id: int, username: str | None) -> tuple[dict[str, object] | None, list[int] | None]:
    acl_ctx = _telegram_client_acl_subject_ctx(db, portal_id, username)
    if not acl_ctx:
        return None, None
    account_scope_ids = _all_account_scope_file_ids(db, portal_id=portal_id, audience="client")
    allowed_ids = _filter_file_ids_by_kb_acl(
        db,
        file_ids=account_scope_ids,
        membership_id=int(acl_ctx.get("membership_id")) if acl_ctx.get("membership_id") else None,
        group_ids=[int(x) for x in (acl_ctx.get("group_ids") or [])],
        role=str(acl_ctx.get("role") or "client"),
        audience="client",
    )
    return acl_ctx, sorted(allowed_ids)


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
    client_acl_ctx = None
    client_file_ids_filter = None

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
    elif kind == "client":
        if not sender_username:
            return {
                "status": "blocked",
                "reason": "acl",
                "detail": "missing_username",
                "reply": MSG_MISSING_USERNAME,
                "chat_id": chat_id,
            }
        client_acl_ctx, client_file_ids_filter = _telegram_client_file_scope(db, portal_id, sender_username)
        if not client_acl_ctx:
            return {
                "status": "blocked",
                "reason": "acl",
                "detail": "no_access",
                "reply": MSG_NO_ACCESS,
                "chat_id": chat_id,
            }
        sender_user_id = client_acl_ctx.get("membership_id")

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
        portal = db.get(Portal, int(portal_id))
        rec = KBFile(
            account_id=int(portal.account_id) if portal and portal.account_id else None,
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
            account_id=rec.account_id,
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
                job_id=f"kbjob:{job.id}",
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
                if client_file_ids_filter == []:
                    rag_answer, rag_err, usage = None, "kb_empty", None
                else:
                    try:
                        response_body = execute_client_flow(
                            db,
                            portal_id,
                            dialog.id,
                            text,
                            file_ids_filter=client_file_ids_filter,
                        )
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
                            file_ids_filter=client_file_ids_filter,
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
                response_body = MSG_NO_CLIENT_MATERIALS if kind == "client" else MSG_KB_EMPTY
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
