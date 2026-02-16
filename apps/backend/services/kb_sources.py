"""KB URL sources: download audio, transcribe, ingest."""
from __future__ import annotations

import os
import re
import subprocess
import httpx
from bs4 import BeautifulSoup  # type: ignore
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.backend.models.kb import KBSource, KBFile, KBJob
from apps.backend.services.kb_storage import ensure_portal_dir
from apps.backend.services.kb_ingest import ingest_file


def _detect_source_type(url: str) -> str:
    u = (url or "").lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "vk.com" in u or "vkvideo.ru" in u:
        return "vk"
    if "rutube.ru" in u:
        return "rutube"
    return "web"


def _safe_filename(name: str) -> str:
    if not name:
        return "source"
    name = re.sub(r"[^\w\-. ]+", "", name, flags=re.U).strip()
    name = re.sub(r"\s+", " ", name).strip()
    return name[:120] if name else "source"


def create_url_source(
    db: Session,
    portal_id: int,
    url: str,
    title: str | None = None,
    *,
    audience: str = "staff",
) -> dict:
    url = (url or "").strip()
    if not url:
        return {"ok": False, "error": "missing_url"}
    if audience not in ("staff", "client"):
        audience = "staff"
    source_type = _detect_source_type(url)
    src = KBSource(
        portal_id=portal_id,
        source_type=source_type,
        audience=audience,
        url=url,
        title=title,
        status="new",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(src)
    db.commit()
    db.refresh(src)
    job = KBJob(
        portal_id=portal_id,
        job_type="source",
        status="queued",
        payload_json={"source_id": src.id},
    )
    db.add(job)
    db.commit()
    return {"ok": True, "source_id": src.id, "job_id": job.id, "source_type": source_type}


def _yt_dlp_download_audio(url: str, out_dir: str) -> tuple[str | None, str | None]:
    """
    Download best audio to out_dir. Returns (file_path, title).
    """
    os.makedirs(out_dir, exist_ok=True)
    title_cmd = ["yt-dlp", "--no-playlist", "--print", "title", url]
    try:
        title = subprocess.check_output(title_cmd, stderr=subprocess.DEVNULL).decode("utf-8", errors="ignore").strip()
    except Exception:
        title = ""
    safe_title = _safe_filename(title) if title else "source"
    out_tpl = os.path.join(out_dir, safe_title + ".%(ext)s")
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-x",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "4",
        "-o",
        out_tpl,
        url,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # find produced file
    for ext in (".mp3", ".m4a", ".webm", ".opus", ".wav"):
        cand = os.path.join(out_dir, safe_title + ext)
        if os.path.exists(cand):
            return cand, title or safe_title
    return None, title or safe_title


def process_url_source(db: Session, source_id: int) -> dict:
    src = db.get(KBSource, source_id)
    if not src:
        return {"ok": False, "error": "source_not_found"}
    src.status = "processing"
    src.updated_at = datetime.utcnow()
    db.add(src)
    db.commit()
    try:
        portal_dir = ensure_portal_dir(src.portal_id)
        if src.source_type == "web":
            r = httpx.get(src.url or "", timeout=20)
            if r.status_code >= 400:
                src.status = "error"
                src.updated_at = datetime.utcnow()
                db.commit()
                return {"ok": False, "error": f"http_{r.status_code}"}
            html = r.text or ""
            soup = BeautifulSoup(html, "lxml")
            for tag in soup(["script", "style", "noscript"]):
                tag.extract()
            title = (soup.title.get_text().strip() if soup.title else "") or (src.title or "")
            text = soup.get_text("\n").strip()
            if not text:
                src.status = "error"
                src.updated_at = datetime.utcnow()
                db.commit()
                return {"ok": False, "error": "no_text"}
            safe_title = _safe_filename(title or "web")
            filename = f"{safe_title}.txt"
            file_path = os.path.join(portal_dir, filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(text)
            rec = KBFile(
                portal_id=src.portal_id,
                source_id=src.id,
                filename=filename,
                audience=src.audience or "staff",
                mime_type="text/plain",
                size_bytes=os.path.getsize(file_path),
                storage_path=file_path,
                sha256=None,
                status="uploaded",
                uploaded_by_type="system",
                uploaded_by_id="source",
                uploaded_by_name=src.source_type or "source",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        else:
            file_path, title = _yt_dlp_download_audio(src.url or "", portal_dir)
            if not file_path:
                src.status = "error"
                src.updated_at = datetime.utcnow()
                db.commit()
                return {"ok": False, "error": "download_failed"}
            filename = os.path.basename(file_path)
            rec = KBFile(
                portal_id=src.portal_id,
                source_id=src.id,
                filename=filename,
                audience=src.audience or "staff",
                mime_type="audio/mpeg",
                size_bytes=os.path.getsize(file_path),
                storage_path=file_path,
                sha256=None,
                status="uploaded",
                uploaded_by_type="system",
                uploaded_by_id="source",
                uploaded_by_name=src.source_type or "source",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        # ingest immediately in worker
        result = ingest_file(db, rec.id, trace_id=None)
        if not result.get("ok"):
            src.status = "error"
            src.updated_at = datetime.utcnow()
            db.commit()
            return {"ok": False, "error": result.get("error") or "ingest_failed"}
        src.status = "ready"
        src.title = title or src.title
        src.updated_at = datetime.utcnow()
        db.commit()
        return {"ok": True, "file_id": rec.id}
    except Exception as e:
        src.status = "error"
        src.updated_at = datetime.utcnow()
        db.commit()
        return {"ok": False, "error": str(e)[:200]}
