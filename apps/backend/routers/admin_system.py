"""Админские endpoints системы."""

import importlib.util
import os

import redis
from fastapi import APIRouter, Depends

from apps.backend.auth import get_current_admin
from apps.backend.config import get_settings

router = APIRouter()


def _diarization_runtime_status() -> dict:
    def _has_module(name: str) -> bool:
        try:
            return importlib.util.find_spec(name) is not None
        except Exception:
            return False

    enabled_by_env = (os.getenv("ENABLE_SPEAKER_DIARIZATION") or "").strip().lower() in ("1", "true", "yes", "on")
    token_present = bool((os.getenv("PYANNOTE_TOKEN") or os.getenv("HUGGINGFACE_TOKEN") or "").strip())
    # Диаризация исполняется в worker-ingest. Backend может быть без heavy ML-пакетов.
    pyannote_backend = _has_module("pyannote.audio")
    torch_backend = _has_module("torch")
    ffmpeg_path = (os.getenv("FFMPEG_BIN_PATH") or "ffmpeg").strip()
    ffprobe_path = (os.getenv("FFPROBE_BIN_PATH") or "ffprobe").strip()

    available = enabled_by_env and token_present
    if not enabled_by_env:
        reason = "disabled_by_env"
    elif not token_present:
        reason = "missing_token"
    else:
        reason = "ok"

    return {
        "available": available,
        "reason": reason,
        "enabled_by_env": enabled_by_env,
        "token_present": token_present,
        "pyannote_installed": available,
        "torch_installed": available,
        "pyannote_backend": pyannote_backend,
        "torch_backend": torch_backend,
        "ffmpeg_bin": ffmpeg_path,
        "ffprobe_bin": ffprobe_path,
    }


@router.get("/health")
def system_health(_: dict = Depends(get_current_admin)):
    s = get_settings()
    status = {"postgres": "unknown", "redis": "unknown"}
    try:
        from sqlalchemy import text

        from apps.backend.database import get_session_factory

        factory = get_session_factory()
        sess = factory()
        sess.execute(text("SELECT 1"))
        sess.close()
        status["postgres"] = "ok"
    except Exception as e:
        status["postgres"] = str(e)
    try:
        r = redis.Redis(host=s.redis_host, port=s.redis_port)
        r.ping()
        status["redis"] = "ok"
    except Exception as e:
        status["redis"] = str(e)
    return status


@router.get("/queue")
def system_queue(_: dict = Depends(get_current_admin)):
    s = get_settings()
    try:
        from rq import Queue, Worker

        r = redis.Redis(host=s.redis_host, port=s.redis_port)
        queue_names: list[str] = []
        for name in (
            s.rq_ingest_queue_name or "ingest",
            s.rq_outbox_queue_name or "outbox",
            "default",
        ):
            if name not in queue_names:
                queue_names.append(name)

        workers = Worker.all(connection=r)
        worker_by_queue: dict[str, int] = {name: 0 for name in queue_names}
        worker_items: list[dict] = []
        for w in workers:
            qnames = [q.name for q in getattr(w, "queues", [])]
            for qn in qnames:
                worker_by_queue[qn] = worker_by_queue.get(qn, 0) + 1
            worker_items.append({"name": w.name, "state": w.get_state(), "queues": qnames})

        queues: list[dict] = []
        for name in queue_names:
            q = Queue(name, connection=r)
            queued = int(q.count or 0)
            started = int(q.started_job_registry.count or 0)
            failed = int(q.failed_job_registry.count or 0)
            deferred = int(q.deferred_job_registry.count or 0)
            scheduled = int(q.scheduled_job_registry.count or 0)
            workers_count = int(worker_by_queue.get(name, 0))
            overloaded = queued > max(0, workers_count * 3)
            queues.append(
                {
                    "queue_name": name,
                    "queued": queued,
                    "started": started,
                    "failed": failed,
                    "deferred": deferred,
                    "scheduled": scheduled,
                    "workers": workers_count,
                    "overloaded": overloaded,
                }
            )

        return {"queues": queues, "workers_total": len(workers), "workers": worker_items}
    except Exception as e:
        return {"error": str(e)}


@router.get("/workers")
def system_workers(_: dict = Depends(get_current_admin)):
    s = get_settings()
    try:
        from rq import Worker

        r = redis.Redis(host=s.redis_host, port=s.redis_port)
        return {
            "workers": [
                {"name": w.name, "state": w.get_state(), "queues": [q.name for q in getattr(w, "queues", [])]}
                for w in Worker.all(connection=r)
            ]
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/diarization")
def system_diarization(_: dict = Depends(get_current_admin)):
    return _diarization_runtime_status()
