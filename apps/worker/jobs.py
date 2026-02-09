"""RQ jobs."""
import json
import logging

logger = logging.getLogger(__name__)


def _split_message(text: str, limit: int = 3000) -> list[str]:
    t = (text or "").strip()
    if not t:
        return []
    if len(t) <= limit:
        return [t]
    parts: list[str] = []
    buf: list[str] = []
    size = 0
    for para in t.split("\n"):
        chunk = (para.strip() + "\n").strip()
        if not chunk:
            continue
        if size + len(chunk) + 1 > limit and buf:
            parts.append("\n".join(buf).strip())
            buf = []
            size = 0
        if len(chunk) > limit:
            for i in range(0, len(chunk), limit):
                parts.append(chunk[i:i + limit])
            continue
        buf.append(chunk)
        size += len(chunk) + 1
    if buf:
        parts.append("\n".join(buf).strip())
    return parts or [t[:limit]]


def process_outbox(outbox_id: int) -> bool:
    """Отправка сообщения через Bitrix API."""
    from apps.backend.database import get_session_factory
    from apps.backend.models.outbox import Outbox
    from apps.backend.clients.bitrix import im_message_add, imbot_message_add
    from apps.backend.services.portal_tokens import ensure_fresh_access_token, BitrixAuthError
    from apps.backend.config import get_settings
    from apps.backend.clients.telegram import telegram_send_message
    from apps.backend.services.telegram_settings import get_portal_telegram_token_plain

    factory = get_session_factory()
    with factory() as db:
        o = db.get(Outbox, outbox_id)
        if not o or o.status != "created":
            return False
        payload = json.loads(o.payload_json or "{}")
        provider = payload.get("provider") or "bitrix"
        if provider == "telegram":
            chat_id = payload.get("chat_id")
            body = payload.get("body")
            kind = payload.get("kind") or "staff"
            if not chat_id or not body:
                o.status = "error"
                o.error_message = "Missing chat_id or body"
                db.commit()
                return False
            token = get_portal_telegram_token_plain(db, o.portal_id, kind)
            if not token:
                o.status = "error"
                o.error_message = "Missing telegram token"
                db.commit()
                return False
            parts = _split_message(body, limit=3500)
            ok = True
            err = None
            for part in parts:
                ok, err = telegram_send_message(token, chat_id, part)
                if not ok:
                    break
            if ok:
                from datetime import datetime
                o.status = "sent"
                o.sent_at = datetime.utcnow()
            else:
                o.status = "error"
                o.error_message = (err or "send_failed")[:200]
                o.retry_count = (o.retry_count or 0) + 1
            db.commit()
            return ok
        dialog_id = payload.get("dialog_id")
        body = payload.get("body")
        domain = payload.get("domain")
        access_token_payload = payload.get("access_token")
        app_token = payload.get("app_token")
        bot_id = payload.get("bot_id", 0)
        if not dialog_id or not body:
            o.status = "error"
            o.error_message = "Missing dialog_id or body"
            db.commit()
            return False
        access_token = access_token_payload or app_token
        if not access_token and o.portal_id:
            try:
                access_token = ensure_fresh_access_token(db, o.portal_id)
            except BitrixAuthError as e:
                access_token = None
                o.status = "error"
                o.error_message = f"auth_error:{e.code}"
                db.commit()
                return False
        if not domain and o.portal_id:
            from apps.backend.models.portal import Portal
            p = db.get(Portal, o.portal_id)
            if p:
                domain = p.domain
        if not access_token or not domain:
            o.status = "error"
            o.error_message = "No token or domain"
            db.commit()
            return False
        domain_clean = domain.replace("https://", "").replace("http://", "").rstrip("/")
        domain_full = f"https://{domain_clean}"
        import time
        trace_id = payload.get("trace_id", "")
        t0 = time.perf_counter()
        parts = _split_message(body, limit=3000)
        ok = True
        err = None
        err_desc = ""
        rest_method = "imbot.message.add" if bot_id else "im.message.add"
        for part in parts:
            if bot_id and access_token:
                ok, err, err_desc = imbot_message_add(domain_full, access_token, int(bot_id), dialog_id, part)
            else:
                ok = im_message_add(domain_full, access_token, dialog_id, part)
                err = None if ok else "send_failed"
                err_desc = ""
            if not ok:
                break
        latency_ms = int((time.perf_counter() - t0) * 1000)
        if trace_id:
            try:
                from apps.backend.services.bitrix_logging import log_outbound
                log_outbound(db, trace_id, o.portal_id, "POST", rest_method, 200 if ok else 500, latency_ms)
            except Exception:
                pass
        if ok:
            from datetime import datetime
            o.status = "sent"
            o.sent_at = datetime.utcnow()
        else:
            o.status = "error"
            if bot_id and app_token:
                o.error_message = f"Bitrix API failed: {err or 'unknown'}"
                if err_desc:
                    o.error_message = (o.error_message + f" ({err_desc})")[:200]
            else:
                o.error_message = "Bitrix API failed"
            o.retry_count = (o.retry_count or 0) + 1
        db.commit()
    return ok


def process_kb_job(job_id: int) -> bool:
    """Process KB job (ingest)."""
    from apps.backend.database import get_session_factory
    from apps.backend.models.kb import KBJob
    from apps.backend.models.outbox import Outbox
    from apps.backend.services.kb_ingest import ingest_file
    from apps.backend.services.kb_sources import process_url_source

    factory = get_session_factory()
    with factory() as db:
        job = db.get(KBJob, job_id)
        if not job or job.status not in ("queued", "processing"):
            return False
        job.status = "processing"
        db.add(job)
        db.commit()
        payload = job.payload_json or {}
        if job.job_type == "source":
            source_id = payload.get("source_id")
            if not source_id:
                job.status = "error"
                job.error_message = "missing_source_id"
                db.add(job)
                db.commit()
                return False
            result = process_url_source(db, int(source_id))
            if not result.get("ok"):
                job.status = "error"
                job.error_message = (result.get("error") or "source_failed")[:200]
                db.add(job)
                db.commit()
                return False
            job.status = "done"
            db.add(job)
            db.commit()
            return True
        if job.job_type != "ingest":
            job.status = "error"
            job.error_message = "unsupported_job_type"
            db.add(job)
            db.commit()
            return False
        file_id = payload.get("file_id")
        if not file_id:
            job.status = "error"
            job.error_message = "missing_file_id"
            db.add(job)
            db.commit()
            return False
        result = ingest_file(db, int(file_id), trace_id=job.trace_id)
        if not result.get("ok"):
            err = (result.get("error") or "ingest_failed")[:200]
            if err == "rate_limited":
                job.status = "queued"
                job.error_message = "rate_limited"
                db.add(job)
                db.commit()
                try:
                    from redis import Redis
                    from rq import Queue
                    from datetime import timedelta
                    from apps.backend.config import get_settings
                    s = get_settings()
                    r = Redis(host=s.redis_host, port=s.redis_port)
                    q = Queue("default", connection=r)
                    q.enqueue_in(timedelta(seconds=30), "apps.worker.jobs.process_kb_job", job.id)
                except Exception:
                    pass
                return False
            job.status = "error"
            job.error_message = err
            db.add(job)
            db.commit()
            return False
        job.status = "done"
        db.add(job)
        db.commit()
        try:
            chat_id = payload.get("tg_chat_id")
            kind = payload.get("tg_kind") or "staff"
            fname = payload.get("tg_filename")
            if chat_id:
                body = f"Изучил ваш документ {fname}, задавайте вопросы! ✅" if fname else "Изучил ваш документ, задавайте вопросы! ✅"
                outbox = Outbox(
                    portal_id=job.portal_id,
                    message_id=None,
                    status="created",
                    payload_json=json.dumps({
                        "provider": "telegram",
                        "kind": kind,
                        "chat_id": chat_id,
                        "body": body,
                    }, ensure_ascii=False),
                )
                db.add(outbox)
                db.commit()
                from redis import Redis
                from rq import Queue
                from apps.backend.config import get_settings
                s = get_settings()
                r = Redis(host=s.redis_host, port=s.redis_port)
                q = Queue("default", connection=r)
                q.enqueue("apps.worker.jobs.process_outbox", outbox.id)
        except Exception:
            pass
        return True
