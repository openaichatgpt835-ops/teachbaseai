"""Health и ready endpoints."""
import redis
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.backend.deps import get_db
from apps.backend.config import get_settings

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "service": "teachbaseai"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)):
    s = get_settings()
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=503)

    try:
        r = redis.Redis(host=s.redis_host, port=s.redis_port)
        r.ping()
    except Exception as e:
        return JSONResponse({"status": "error", "detail": f"redis: {e}"}, status_code=503)

    return {"status": "ok"}
