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
        r = redis.Redis(host=s.redis_host, port=s.redis_port)
        q = r.llen("rq:queue:default")
        return {"queue_length": q, "queue_name": "default"}
    except Exception as e:
        return {"error": str(e)}


@router.get("/workers")
def system_workers(_: dict = Depends(get_current_admin)):
    s = get_settings()
    try:
        r = redis.Redis(host=s.redis_host, port=s.redis_port)
        workers = r.smembers("rq:workers")
        return {"workers": [w.decode() if isinstance(w, bytes) else w for w in workers]}
    except Exception as e:
        return {"error": str(e)}
