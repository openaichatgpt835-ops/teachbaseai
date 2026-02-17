"""Recovery loop for stuck KB ingest jobs/files."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from apps.backend.config import get_settings
from apps.backend.database import get_session_factory
from apps.backend.models.kb import KBFile, KBJob

logger = logging.getLogger(__name__)
_WATCHDOG_LOCK_KEY = "kb_watchdog:lock"


def _extract_file_id(job: KBJob) -> int | None:
    payload = job.payload_json or {}
    file_id = payload.get("file_id")
    if file_id is None:
        return None
    try:
        return int(file_id)
    except Exception:
        return None


def _active_ingest_files(db, exclude_job_ids: set[int] | None = None) -> set[int]:
    exclude_job_ids = exclude_job_ids or set()
    jobs = db.execute(
        select(KBJob).where(
            KBJob.job_type == "ingest",
            KBJob.status.in_(("queued", "processing")),
        )
    ).scalars().all()
    out: set[int] = set()
    for job in jobs:
        if job.id in exclude_job_ids:
            continue
        file_id = _extract_file_id(job)
        if file_id is not None:
            out.add(file_id)
    return out


def recover_stuck_kb_jobs_once(
    stale_seconds: int = 600,
    batch_limit: int = 200,
) -> dict:
    """Requeue stale processing jobs/files and return counters."""
    factory = get_session_factory()
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=max(60, int(stale_seconds)))
    requeued_ids: list[int] = []
    stuck_job_ids: set[int] = set()
    result = {
        "stuck_jobs_failed": 0,
        "files_requeued": 0,
        "jobs_created": 0,
        "queued_jobs_enqueued": 0,
    }

    with factory() as db:
        stuck_jobs = db.execute(
            select(KBJob).where(
                KBJob.status == "processing",
                KBJob.updated_at < cutoff,
            ).limit(batch_limit)
        ).scalars().all()
        for job in stuck_jobs:
            job.status = "failed"
            job.error_message = "stuck_processing_timeout"
            db.add(job)
            stuck_job_ids.add(job.id)
            result["stuck_jobs_failed"] += 1
        db.commit()

        active_file_ids = _active_ingest_files(db, exclude_job_ids=stuck_job_ids)

        # Requeue files affected by stuck jobs.
        for job in stuck_jobs:
            if job.job_type != "ingest":
                continue
            file_id = _extract_file_id(job)
            if file_id is None or file_id in active_file_ids:
                continue
            file_rec = db.get(KBFile, file_id)
            if not file_rec:
                continue
            file_rec.status = "queued"
            file_rec.error_message = None
            db.add(file_rec)
            new_job = KBJob(
                portal_id=file_rec.portal_id,
                job_type="ingest",
                status="queued",
                payload_json={"file_id": file_id},
            )
            db.add(new_job)
            db.flush()
            requeued_ids.append(new_job.id)
            active_file_ids.add(file_id)
            result["files_requeued"] += 1
            result["jobs_created"] += 1

        # Also recover files stuck in processing with no active ingest jobs.
        stale_files = db.execute(
            select(KBFile).where(
                KBFile.status == "processing",
                KBFile.updated_at < cutoff,
            ).limit(batch_limit)
        ).scalars().all()
        for file_rec in stale_files:
            if file_rec.id in active_file_ids:
                continue
            file_rec.status = "queued"
            file_rec.error_message = None
            db.add(file_rec)
            new_job = KBJob(
                portal_id=file_rec.portal_id,
                job_type="ingest",
                status="queued",
                payload_json={"file_id": file_rec.id},
            )
            db.add(new_job)
            db.flush()
            requeued_ids.append(new_job.id)
            active_file_ids.add(file_rec.id)
            result["files_requeued"] += 1
            result["jobs_created"] += 1

        # Recover files stuck in uploaded state (job enqueue missed/faulted).
        stale_uploaded_files = db.execute(
            select(KBFile).where(
                KBFile.status == "uploaded",
                KBFile.updated_at < cutoff,
            ).limit(batch_limit)
        ).scalars().all()
        for file_rec in stale_uploaded_files:
            if file_rec.id in active_file_ids:
                continue
            file_rec.status = "queued"
            file_rec.error_message = None
            db.add(file_rec)
            new_job = KBJob(
                portal_id=file_rec.portal_id,
                job_type="ingest",
                status="queued",
                payload_json={"file_id": file_rec.id},
            )
            db.add(new_job)
            db.flush()
            requeued_ids.append(new_job.id)
            active_file_ids.add(file_rec.id)
            result["files_requeued"] += 1
            result["jobs_created"] += 1

        db.commit()

    enqueue_ids: list[int] = list(requeued_ids)

    # Safety net: ensure queued ingest jobs are present in Redis queue.
    with factory() as db:
        queued_ids = db.execute(
            select(KBJob.id).where(
                KBJob.job_type == "ingest",
                KBJob.status == "queued",
            ).order_by(KBJob.created_at.asc()).limit(batch_limit)
        ).scalars().all()
        for qid in queued_ids:
            if int(qid) not in enqueue_ids:
                enqueue_ids.append(int(qid))
        result["queued_jobs_enqueued"] = len(queued_ids)

    if enqueue_ids:
        try:
            from redis import Redis
            from rq import Queue

            s = get_settings()
            r = Redis(host=s.redis_host, port=s.redis_port)
            q = Queue(s.rq_ingest_queue_name or "ingest", connection=r)
            job_timeout = max(300, int(s.kb_job_timeout_seconds or 3600))
            for job_id in enqueue_ids:
                q.enqueue("apps.worker.jobs.process_kb_job", job_id, job_timeout=job_timeout)
        except Exception:
            logger.exception("kb_watchdog_enqueue_failed")

    return result


def run_kb_watchdog_cycle() -> dict:
    """Single guarded watchdog cycle with Redis lock."""
    s = get_settings()
    try:
        from redis import Redis

        r = Redis(host=s.redis_host, port=s.redis_port)
        lock_ttl = max(30, int((s.kb_watchdog_interval_seconds or 120) * 0.9))
        if not r.set(_WATCHDOG_LOCK_KEY, "1", nx=True, ex=lock_ttl):
            return {"skipped": "lock_not_acquired"}
    except Exception:
        # If Redis lock is unavailable, still try to recover once.
        logger.exception("kb_watchdog_lock_unavailable")
    try:
        return recover_stuck_kb_jobs_once(
            stale_seconds=s.kb_processing_stale_seconds,
            batch_limit=s.kb_watchdog_batch_limit,
        )
    except Exception:
        logger.exception("kb_watchdog_cycle_failed")
        return {"error": "watchdog_failed"}
