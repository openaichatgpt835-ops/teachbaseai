"""RQ jobs."""
import json
import logging
from datetime import timedelta
from sqlalchemy import select

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
    """Process KB job (ingest/source) with safe lifecycle and dedup."""
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

        def _set_job(status: str, error: str | None = None) -> None:
            db.refresh(job)
            job.status = status
            job.error_message = (error or "")[:200] or None
            db.add(job)
            db.commit()

        job.status = "processing"
        job.error_message = None
        db.add(job)
        db.commit()
        payload = job.payload_json or {}

        try:
            if job.job_type == "source":
                source_id = payload.get("source_id")
                if not source_id:
                    _set_job("error", "missing_source_id")
                    return False
                result = process_url_source(db, int(source_id))
                if not result.get("ok"):
                    _set_job("error", (result.get("error") or "source_failed")[:200])
                    return False
                _set_job("done")
                return True

            if job.job_type != "ingest":
                _set_job("error", "unsupported_job_type")
                return False

            file_id_raw = payload.get("file_id")
            if not file_id_raw:
                _set_job("error", "missing_file_id")
                return False
            file_id = int(file_id_raw)

            # Skip duplicate active jobs for the same file.
            active_jobs = db.execute(
                select(KBJob).where(
                    KBJob.job_type == "ingest",
                    KBJob.status.in_(("queued", "processing")),
                    KBJob.id != job.id,
                )
            ).scalars().all()
            duplicate_job_id = None
            for other in active_jobs:
                other_file_id = (other.payload_json or {}).get("file_id")
                if other_file_id is None:
                    continue
                try:
                    if int(other_file_id) == file_id:
                        duplicate_job_id = other.id
                        break
                except Exception:
                    continue
            if duplicate_job_id:
                _set_job("done", f"duplicate_skipped:{duplicate_job_id}")
                return True

            result = ingest_file(db, file_id, trace_id=job.trace_id)
            if not result.get("ok"):
                err = (result.get("error") or "ingest_failed")[:200]
                if err == "rate_limited":
                    _set_job("queued", "rate_limited")
                    try:
                        from redis import Redis
                        from rq import Queue
                        from apps.backend.config import get_settings
                        s = get_settings()
                        r = Redis(host=s.redis_host, port=s.redis_port)
                        q = Queue("default", connection=r)
                        q.enqueue_in(timedelta(seconds=30), "apps.worker.jobs.process_kb_job", job.id)
                    except Exception:
                        pass
                    return False
                _set_job("error", err)
                return False

            _set_job("done")

            # Telegram notify uploader when ingestion finished.
            try:
                chat_id = payload.get("tg_chat_id")
                kind = payload.get("tg_kind") or "staff"
                fname = payload.get("tg_filename")
                if chat_id:
                    body = (
                        f"\u0418\u0437\u0443\u0447\u0438\u043b \u0432\u0430\u0448 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442 {fname}, "
                        f"\u0437\u0430\u0434\u0430\u0432\u0430\u0439\u0442\u0435 \u0432\u043e\u043f\u0440\u043e\u0441\u044b! \u2705"
                    ) if fname else (
                        "\u0418\u0437\u0443\u0447\u0438\u043b \u0432\u0430\u0448 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442, "
                        "\u0437\u0430\u0434\u0430\u0432\u0430\u0439\u0442\u0435 \u0432\u043e\u043f\u0440\u043e\u0441\u044b! \u2705"
                    )
                    outbox = Outbox(
                        portal_id=job.portal_id,
                        message_id=None,
                        status="created",
                        payload_json=json.dumps(
                            {
                                "provider": "telegram",
                                "kind": kind,
                                "chat_id": chat_id,
                                "body": body,
                            },
                            ensure_ascii=False,
                        ),
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
        except Exception as exc:
            logger.exception("process_kb_job_failed job_id=%s", job_id)
            try:
                db.rollback()
            except Exception:
                pass
            try:
                job_fresh = db.get(KBJob, job_id)
                if job_fresh:
                    job_fresh.status = "error"
                    job_fresh.error_message = ("worker_exception:" + str(exc))[:200]
                    db.add(job_fresh)
                    db.commit()
            except Exception:
                pass
            return False

