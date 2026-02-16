"""Admin KB endpoints: upload, list, credentials."""
import os
import uuid
from datetime import datetime
import logging
import hashlib

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from apps.backend.deps import get_db
from apps.backend.auth import get_current_admin
from apps.backend.models.kb import KBFile, KBJob
from apps.backend.services.kb_storage import ensure_portal_dir, save_upload
from apps.backend.services.kb_settings import (
    get_gigachat_settings,
    set_gigachat_settings,
    get_gigachat_auth_key_plain,
    get_gigachat_access_token_plain,
    get_portal_kb_settings,
    set_portal_kb_settings,
    get_bot_settings,
    set_bot_settings,
)
from apps.backend.services.token_crypto import mask_token
from apps.backend.services.gigachat_client import request_access_token, request_access_token_detailed, list_models, DEFAULT_API_BASE

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/credentials")
def kb_get_credentials(
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return get_gigachat_settings(db)


@router.post("/credentials")
def kb_set_credentials(
    api_base: str | None = Form(None),
    model: str | None = Form(None),
    embedding_model: str | None = Form(None),
    chat_model: str | None = Form(None),
    client_id: str | None = Form(None),
    auth_key: str | None = Form(None),
    scope: str | None = Form(None),
    client_secret: str | None = Form(None),
    access_token: str | None = Form(None),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    before_plain = get_gigachat_auth_key_plain(db)
    auth_key_input = (auth_key or "").strip()
    auth_key_input_sha = (
        hashlib.sha256(auth_key_input.encode()).hexdigest()[:12] if auth_key_input else ""
    )
    auth_key_input_masked = mask_token(auth_key_input) if auth_key_input else ""
    logger.warning(
        "gigachat_auth_key_input %s",
        {
            "input_present": bool(auth_key_input),
            "input_len": len(auth_key_input),
            "input_masked": auth_key_input_masked,
            "input_sha12": auth_key_input_sha,
        },
    )
    # Используем нормализованный ввод, чтобы исключить пустые/трейлинг пробелы
    auth_key_to_save = auth_key_input if auth_key_input else None
    out = set_gigachat_settings(
        db,
        api_base,
        model,
        embedding_model,
        chat_model,
        client_id,
        auth_key_to_save,
        scope,
        client_secret,
        access_token,
    )
    after_plain = get_gigachat_auth_key_plain(db)
    auth_key_updated = bool(after_plain and after_plain != before_plain)
    after_sha = hashlib.sha256(after_plain.encode()).hexdigest()[:12] if after_plain else ""
    logger.warning(
        "gigachat_auth_key_saved %s",
        {
            "updated": auth_key_updated,
            "before_masked": mask_token(before_plain) if before_plain else "",
            "after_masked": mask_token(after_plain) if after_plain else "",
            "before_len": len(before_plain) if before_plain else 0,
            "after_len": len(after_plain) if after_plain else 0,
            "input_sha12": auth_key_input_sha,
            "after_sha12": after_sha,
        },
    )
    auth_plain = get_gigachat_auth_key_plain(db)
    scope_val = (out.get("scope") or "").strip()
    if not auth_plain or not scope_val:
        out["auth_key_updated"] = auth_key_updated
        out["auth_key_input_masked"] = auth_key_input_masked
        out["auth_key_input_len"] = len(auth_key_input) if auth_key_input else 0
        out["auth_key_input_sha12"] = auth_key_input_sha
        out["auth_key_sha12"] = after_sha
        out["auth_key_mismatch"] = bool(auth_key_input_sha and after_sha and auth_key_input_sha != after_sha)
        return out
    token, expires_at, err = request_access_token(auth_plain, scope_val)
    if err:
        out["token_error"] = err
        out["auth_key_updated"] = auth_key_updated
        out["auth_key_input_masked"] = auth_key_input_masked
        out["auth_key_input_len"] = len(auth_key_input) if auth_key_input else 0
        out["auth_key_input_sha12"] = auth_key_input_sha
        out["auth_key_sha12"] = after_sha
        out["auth_key_mismatch"] = bool(auth_key_input_sha and after_sha and auth_key_input_sha != after_sha)
        return out
    set_gigachat_settings(
        db,
        api_base=None,
        model=None,
        embedding_model=None,
        chat_model=None,
        client_id=None,
        auth_key=None,
        scope=None,
        client_secret=None,
        access_token=token,
        access_token_expires_at=expires_at,
    )
    out = get_gigachat_settings(db)
    out["token_error"] = None
    out["auth_key_updated"] = auth_key_updated
    out["auth_key_input_masked"] = auth_key_input_masked
    out["auth_key_input_len"] = len(auth_key_input) if auth_key_input else 0
    out["auth_key_input_sha12"] = auth_key_input_sha
    out["auth_key_sha12"] = after_sha
    out["auth_key_mismatch"] = bool(auth_key_input_sha and after_sha and auth_key_input_sha != after_sha)
    return out


@router.post("/token/refresh")
def kb_refresh_token(
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    settings = get_gigachat_settings(db)
    auth_key = get_gigachat_auth_key_plain(db)
    scope = settings.get("scope") or ""
    token, expires_at, err, _status = request_access_token_detailed(auth_key, scope)
    if err:
        raise HTTPException(status_code=400, detail=err)
    set_gigachat_settings(
        db,
        api_base=None,
        model=None,
        embedding_model=None,
        chat_model=None,
        client_id=None,
        auth_key=None,
        scope=None,
        client_secret=None,
        access_token=token,
        access_token_expires_at=expires_at,
    )
    out = get_gigachat_settings(db)
    return {"ok": True, "access_token_expires_at": out.get("access_token_expires_at")}


@router.post("/token/debug")
def kb_debug_token(
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    settings = get_gigachat_settings(db)
    auth_key = get_gigachat_auth_key_plain(db)
    scope = settings.get("scope") or ""
    token, expires_at, err, status = request_access_token_detailed(auth_key, scope)
    return {
        "ok": bool(token),
        "status": status,
        "error": err,
        "access_token_expires_at": expires_at,
    }


@router.get("/models")
def kb_list_models(
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    settings = get_gigachat_settings(db)
    access_token = get_gigachat_access_token_plain(db)
    api_base = settings.get("api_base") or DEFAULT_API_BASE
    expires_at = settings.get("access_token_expires_at") or 0
    if not access_token or (expires_at and expires_at <= int(datetime.utcnow().timestamp())):
        auth_key = get_gigachat_auth_key_plain(db)
        scope = settings.get("scope") or ""
        token, new_exp, err = request_access_token(auth_key, scope)
        if err:
            raise HTTPException(status_code=400, detail=err)
        set_gigachat_settings(
            db,
            api_base=None,
            model=None,
            embedding_model=None,
            chat_model=None,
            client_id=None,
            auth_key=None,
            scope=None,
            client_secret=None,
            access_token=token,
            access_token_expires_at=new_exp,
        )
        access_token = token or ""
    items, err = list_models(api_base, access_token)
    if err and ("401" in err.lower() or "unauthorized" in err.lower()):
        auth_key = get_gigachat_auth_key_plain(db)
        scope = settings.get("scope") or ""
        token, new_exp, err2 = request_access_token(auth_key, scope)
        if err2:
            raise HTTPException(status_code=400, detail=err2)
        set_gigachat_settings(
            db,
            api_base=None,
            model=None,
            embedding_model=None,
            chat_model=None,
            client_id=None,
            auth_key=None,
            scope=None,
            client_secret=None,
            access_token=token,
            access_token_expires_at=new_exp,
        )
        access_token = token or ""
        items, err = list_models(api_base, access_token)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return {"items": items}


@router.get("/files")
def kb_list_files(
    portal_id: int | None = None,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    q = select(KBFile)
    if portal_id:
        q = q.where(KBFile.portal_id == portal_id)
    q = q.order_by(desc(KBFile.id)).limit(200)
    files = db.execute(q).scalars().all()
    return {
        "items": [
            {
                "id": f.id,
                "portal_id": f.portal_id,
                "filename": f.filename,
                "mime_type": f.mime_type,
                "size_bytes": f.size_bytes,
                "status": f.status,
                "error_message": f.error_message,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in files
        ]
    }


@router.get("/portals/{portal_id}/settings")
def kb_get_portal_settings(
    portal_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return get_portal_kb_settings(db, portal_id)


@router.post("/portals/{portal_id}/settings")
def kb_set_portal_settings(
    portal_id: int,
    embedding_model: str | None = Form(None),
    chat_model: str | None = Form(None),
    api_base: str | None = Form(None),
    prompt_preset: str | None = Form(None),
    temperature: float | None = Form(None),
    max_tokens: int | None = Form(None),
    top_p: float | None = Form(None),
    presence_penalty: float | None = Form(None),
    frequency_penalty: float | None = Form(None),
    allow_general: bool | None = Form(None),
    strict_mode: bool | None = Form(None),
    context_messages: int | None = Form(None),
    context_chars: int | None = Form(None),
    retrieval_top_k: int | None = Form(None),
    retrieval_max_chars: int | None = Form(None),
    lex_boost: float | None = Form(None),
    use_history: bool | None = Form(None),
    use_cache: bool | None = Form(None),
    system_prompt_extra: str | None = Form(None),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return set_portal_kb_settings(
        db,
        portal_id,
        embedding_model,
        chat_model,
        api_base,
        prompt_preset,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
        allow_general=allow_general,
        strict_mode=strict_mode,
        context_messages=context_messages,
        context_chars=context_chars,
        retrieval_top_k=retrieval_top_k,
        retrieval_max_chars=retrieval_max_chars,
        lex_boost=lex_boost,
        use_history=use_history,
        use_cache=use_cache,
        system_prompt_extra=system_prompt_extra,
    )


@router.get("/bot/settings")
def admin_get_bot_settings(
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return get_bot_settings(db)


class BotSettingsBody(BaseModel):
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    allow_general: bool | None = None
    strict_mode: bool | None = None
    context_messages: int | None = None
    context_chars: int | None = None
    retrieval_top_k: int | None = None
    retrieval_max_chars: int | None = None
    lex_boost: float | None = None
    use_history: bool | None = None
    use_cache: bool | None = None
    system_prompt_extra: str | None = None


@router.post("/bot/settings")
def admin_set_bot_settings(
    body: BotSettingsBody,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    return set_bot_settings(db, data)


@router.post("/files/upload")
def kb_upload_file(
    portal_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не задан")
    portal_dir = ensure_portal_dir(portal_id)
    safe_name = os.path.basename(file.filename)
    suffix = uuid.uuid4().hex[:8]
    dst_path = os.path.join(portal_dir, f"{suffix}_{safe_name}")
    size, sha256 = save_upload(file.file, dst_path)
    rec = KBFile(
        portal_id=portal_id,
        filename=safe_name,
        mime_type=file.content_type,
        size_bytes=size,
        storage_path=dst_path,
        sha256=sha256,
        status="uploaded",
        uploaded_by_type="admin",
        uploaded_by_id=str(admin.get("sub") or ""),
        uploaded_by_name=str(admin.get("sub") or "admin"),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"id": rec.id, "status": rec.status}


@router.post("/files/{file_id}/process")
def kb_process_file(
    file_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    rec = db.get(KBFile, file_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Файл не найден")
    rec.status = "queued"
    job = KBJob(
        portal_id=rec.portal_id,
        job_type="ingest",
        status="queued",
        payload_json={"file_id": rec.id},
    )
    db.add(job)
    db.commit()
    try:
        from redis import Redis
        from rq import Queue
        from apps.backend.config import get_settings
        s = get_settings()
        r = Redis(host=s.redis_host, port=s.redis_port)
        q = Queue("default", connection=r)
        q.enqueue("apps.worker.jobs.process_kb_job", job.id, job_timeout=1800)
    except Exception:
        pass
    return {"job_id": job.id, "status": job.status}
