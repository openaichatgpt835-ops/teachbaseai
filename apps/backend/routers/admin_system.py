"""Админские endpoints системы."""
import redis
from fastapi import APIRouter, Depends

from apps.backend.deps import get_db
from apps.backend.auth import get_current_admin
from apps.backend.config import get_settings

router = APIRouter()


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
        workers = Worker.all(connection=r)
        return {
            "workers": [
                {"name": w.name, "state": w.get_state(), "queues": [q.name for q in getattr(w, "queues", [])]}
                for w in workers
            ]
        }
    except Exception as e:
        return {"error": str(e)}
