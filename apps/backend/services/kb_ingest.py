"""KB ingestion: parse files, chunk text, generate embeddings."""
from __future__ import annotations

import csv
import hashlib
import os
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from apps.backend.models.kb import KBFile, KBChunk, KBEmbedding
from apps.backend.services.kb_settings import get_effective_gigachat_settings, get_valid_gigachat_access_token
from apps.backend.services.gigachat_client import create_embeddings
from apps.backend.services.billing import get_pricing, calc_cost_rub, record_usage


def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _read_csv_file(path: str) -> str:
    lines: list[str] = []
    with open(path, "r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            lines.append(" | ".join(str(c).strip() for c in row if c is not None))
    return "\n".join(lines)


def _read_xlsx_file(path: str) -> str:
    import openpyxl  # type: ignore
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    lines: list[str] = []
    try:
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                if not row:
                    continue
                line = " | ".join(str(c).strip() for c in row if c is not None)
                if line:
                    lines.append(line)
    finally:
        wb.close()
    return "\n".join(lines)


def _read_xls_file(path: str) -> str:
    import xlrd  # type: ignore
    book = xlrd.open_workbook(path)
    lines: list[str] = []
    for sheet in book.sheets():
        for r in range(sheet.nrows):
            row = sheet.row_values(r)
            line = " | ".join(str(c).strip() for c in row if c is not None and str(c).strip())
            if line:
                lines.append(line)
    return "\n".join(lines)


def _read_docx_file(path: str) -> str:
    import docx  # type: ignore
    d = docx.Document(path)
    parts: list[str] = []
    for p in d.paragraphs:
        if p.text and p.text.strip():
            parts.append(p.text.strip())
    return "\n".join(parts)


def _read_pdf_file(path: str) -> str:
    from pypdf import PdfReader  # type: ignore
    reader = PdfReader(path)
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text.strip())
    return "\n".join(parts)


def _read_pdf_pages(path: str) -> list[tuple[int, str]]:
    from pypdf import PdfReader  # type: ignore
    reader = PdfReader(path)
    out: list[tuple[int, str]] = []
    for idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            out.append((idx, text.strip()))
    return out


def _read_epub_file(path: str) -> str:
    from ebooklib import epub, ITEM_DOCUMENT  # type: ignore
    from bs4 import BeautifulSoup  # type: ignore
    book = epub.read_epub(path)
    parts: list[str] = []
    for item in book.get_items():
        item_type = item.get_type() if hasattr(item, "get_type") else None
        media_type = getattr(item, "media_type", "") or ""
        is_doc = (item_type == ITEM_DOCUMENT) or media_type in ("application/xhtml+xml", "text/html")
        if is_doc:
            soup = BeautifulSoup(item.get_body_content(), "lxml")
            text = soup.get_text("\n").strip()
            if text:
                parts.append(text)
    return "\n".join(parts)


def _read_fb2_file(path: str) -> str:
    from bs4 import BeautifulSoup  # type: ignore
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        data = f.read()
    soup = BeautifulSoup(data, "lxml-xml")
    texts = []
    for p in soup.find_all(["p", "subtitle", "title"]):
        t = (p.get_text() or "").strip()
        if t:
            texts.append(t)
    return "\n".join(texts)


def _ocr_pdf_file(path: str, lang: str = "rus+eng") -> str:
    from pdf2image import convert_from_path  # type: ignore
    import pytesseract  # type: ignore
    pages = convert_from_path(path, dpi=200)
    parts: list[str] = []
    for img in pages:
        text = pytesseract.image_to_string(img, lang=lang) or ""
        if text.strip():
            parts.append(text.strip())
    return "\n".join(parts)


_VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".mp3", ".wav", ".m4a", ".aac", ".flac"}


@dataclass
class _Segment:
    text: str
    start_ms: int
    end_ms: int


def _extract_audio_to_wav(src_path: str, dst_path: str) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        src_path,
        "-ac",
        "1",
        "-ar",
        "16000",
        dst_path,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


_WHISPER_MODEL = None


def _get_whisper_model():
    global _WHISPER_MODEL
    if _WHISPER_MODEL is not None:
        return _WHISPER_MODEL
    from faster_whisper import WhisperModel  # type: ignore
    size = (os.getenv("WHISPER_MODEL_SIZE") or "medium").strip()
    _WHISPER_MODEL = WhisperModel(size, device="cpu", compute_type="int8")
    return _WHISPER_MODEL


def _transcribe_media(path: str) -> list[_Segment]:
    model = _get_whisper_model()
    segments, _info = model.transcribe(path, vad_filter=True)
    out: list[_Segment] = []
    for seg in segments:
        text = (seg.text or "").strip()
        if not text:
            continue
        start_ms = int((seg.start or 0) * 1000)
        end_ms = int((seg.end or 0) * 1000)
        out.append(_Segment(text=text, start_ms=start_ms, end_ms=end_ms))
    return out


def _chunk_segments(segments: list[_Segment], max_chars: int = 1200) -> list[_Segment]:
    if not segments:
        return []
    chunks: list[_Segment] = []
    buf = ""
    start_ms = None
    end_ms = None
    for seg in segments:
        if not buf:
            buf = seg.text
            start_ms = seg.start_ms
            end_ms = seg.end_ms
            continue
        if len(buf) + 1 + len(seg.text) <= max_chars:
            buf = buf + " " + seg.text
            end_ms = seg.end_ms
            continue
        chunks.append(_Segment(text=buf, start_ms=start_ms or 0, end_ms=end_ms or (start_ms or 0)))
        buf = seg.text
        start_ms = seg.start_ms
        end_ms = seg.end_ms
    if buf:
        chunks.append(_Segment(text=buf, start_ms=start_ms or 0, end_ms=end_ms or (start_ms or 0)))
    return chunks


def extract_text_from_file(path: str, mime_type: str | None, filename: str) -> str:
    ext = os.path.splitext(filename.lower())[1]
    if ext in (".txt", ".md"):
        return _read_text_file(path)
    if ext in (".csv",):
        return _read_csv_file(path)
    if ext in (".docx",):
        return _read_docx_file(path)
    if ext in (".pdf",):
        return _read_pdf_file(path)
    if ext in (".epub",):
        return _read_epub_file(path)
    if ext in (".fb2",):
        return _read_fb2_file(path)
    if ext in (".xlsx",):
        return _read_xlsx_file(path)
    if ext in (".xls",):
        return _read_xls_file(path)
    raise ValueError(f"unsupported_file_type:{ext or mime_type or 'unknown'}")


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 200) -> list[str]:
    cleaned = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not cleaned:
        return []
    if max_chars < 200:
        max_chars = 200
    if overlap < 0:
        overlap = 0
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + max_chars)
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(cleaned):
            break
        start = max(0, end - overlap)
        if start == end:
            break
    return chunks


def chunk_text_with_page(text: str, page_num: int, max_chars: int = 1200, overlap: int = 200) -> list[tuple[str, int]]:
    return [(c, page_num) for c in chunk_text(text, max_chars=max_chars, overlap=overlap)]


def _count_tokens_approx(text: str) -> int:
    return len((text or "").split())


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ingest_file(db: Session, file_id: int, trace_id: str | None = None) -> dict:
    rec = db.get(KBFile, file_id)
    if not rec:
        return {"ok": False, "error": "file_not_found"}
    rec.status = "processing"
    rec.error_message = None
    db.add(rec)
    db.commit()

    # reuse existing chunks if they already exist (multi-version embeddings)
    chunk_rows = db.execute(
        select(KBChunk).where(KBChunk.file_id == rec.id).order_by(KBChunk.chunk_index)
    ).scalars().all()

    if not chunk_rows:
        ext = os.path.splitext(rec.filename.lower())[1]
        ocr_enabled = (os.getenv("OCR_ENABLED") or "").strip().lower() in ("1", "true", "yes", "on")
        if ext in _VIDEO_EXTS:
            try:
                with tempfile.TemporaryDirectory() as td:
                    wav_path = os.path.join(td, "audio.wav")
                    _extract_audio_to_wav(rec.storage_path, wav_path)
                    segments = _transcribe_media(wav_path)
                chunks = _chunk_segments(segments)
                transcript_path = rec.storage_path + ".transcript.txt"
                with open(transcript_path, "w", encoding="utf-8") as tf:
                    for seg in segments:
                        tf.write(f"[{seg.start_ms}-{seg.end_ms}] {seg.text}\n")
            except Exception as e:
                rec.status = "error"
                rec.error_message = ("transcribe_failed:" + str(e))[:200]
                db.add(rec)
                db.commit()
                return {"ok": False, "error": "transcribe_failed", "detail": rec.error_message}
        else:
            try:
                if ext == ".pdf":
                    page_texts = _read_pdf_pages(rec.storage_path)
                    chunks = []
                    for page_num, page_text in page_texts:
                        chunks.extend(chunk_text_with_page(page_text, page_num))
                    if not chunks:
                        text = ""
                    else:
                        text = None
                else:
                    text = extract_text_from_file(rec.storage_path, rec.mime_type, rec.filename)
            except Exception as e:
                rec.status = "error"
                rec.error_message = str(e)[:200]
                db.add(rec)
                db.commit()
                return {"ok": False, "error": "extract_failed", "detail": rec.error_message}
            if ext != ".pdf":
                if ext in (".csv", ".xls", ".xlsx"):
                    chunks = chunk_text(text, max_chars=600, overlap=100)
                else:
                    chunks = chunk_text(text)

        if not chunks and ext == ".pdf":
            if ocr_enabled:
                try:
                    text = _ocr_pdf_file(rec.storage_path)
                    chunks = chunk_text(text)
                except Exception as e:
                    rec.status = "error"
                    rec.error_message = ("ocr_failed:" + str(e))[:200]
                    db.add(rec)
                    db.commit()
                    return {"ok": False, "error": "ocr_failed", "detail": rec.error_message}
            else:
                rec.status = "error"
                rec.error_message = "no_text_chunks (ocr_disabled)"
                db.add(rec)
                db.commit()
                return {"ok": False, "error": "no_text_chunks"}
        if not chunks:
            rec.status = "error"
            rec.error_message = "no_text_chunks_after_ocr" if ocr_enabled else "no_text_chunks"
            db.add(rec)
            db.commit()
            return {"ok": False, "error": "no_text_chunks"}

        new_rows: list[KBChunk] = []
        for idx, ch in enumerate(chunks):
            if isinstance(ch, _Segment):
                text_val = ch.text
                start_ms = ch.start_ms
                end_ms = ch.end_ms
                page_num = None
            elif isinstance(ch, tuple) and len(ch) == 2:
                text_val = ch[0]
                start_ms = None
                end_ms = None
                page_num = int(ch[1])
            else:
                text_val = ch
                start_ms = None
                end_ms = None
                page_num = None
            new_rows.append(KBChunk(
                portal_id=rec.portal_id,
                file_id=rec.id,
                chunk_index=idx,
                text=text_val,
                token_count=_count_tokens_approx(text_val),
                sha256=_sha256_text(text_val),
                start_ms=start_ms,
                end_ms=end_ms,
                page_num=page_num,
                created_at=datetime.utcnow(),
            ))
        db.add_all(new_rows)
        db.commit()
        chunk_rows = new_rows

    settings = get_effective_gigachat_settings(db, rec.portal_id)
    model = (settings.get("embedding_model") or settings.get("model") or "").strip()
    api_base = (settings.get("api_base") or "").strip()
    if not model:
        rec.status = "error"
        rec.error_message = "missing_embedding_model"
        db.add(rec)
        db.commit()
        return {"ok": False, "error": "missing_embedding_model"}
    token, err = get_valid_gigachat_access_token(db)
    if err or not token:
        rec.status = "error"
        rec.error_message = err or "missing_access_token"
        db.add(rec)
        db.commit()
        return {"ok": False, "error": rec.error_message}

    # remove existing embeddings for this model only (keep other models)
    chunk_ids = [c.id for c in chunk_rows]
    if chunk_ids:
        db.execute(delete(KBEmbedding).where(
            KBEmbedding.chunk_id.in_(chunk_ids),
            KBEmbedding.model == model,
        ))
        db.commit()

    vectors: list[list[float]] = []
    usage_tokens_total = 0
    base_batch = 6
    # retry with backoff on 429 (rate limit)
    retry_delays = [2, 4, 8]
    for i in range(0, len(chunk_rows), base_batch):
        batch = chunk_rows[i:i + base_batch]
        texts = [c.text for c in batch]
        embeds = None
        err = None
        # try with shrinking batch sizes on retry
        batch_sizes = [len(texts), max(1, len(texts) // 2), 1]
        for attempt, delay in enumerate([0] + retry_delays):
            if delay:
                import time
                time.sleep(delay)
            size = batch_sizes[min(attempt, len(batch_sizes) - 1)]
            subset = texts[:size]
            embeds, err, usage = create_embeddings(api_base, token, model, subset)
            if err and "401" in err:
                token, err2 = get_valid_gigachat_access_token(db, force_refresh=True)
                if token and not err2:
                    embeds, err, usage = create_embeddings(api_base, token, model, subset)
            if err and "429" in err:
                continue
            if err:
                break
            if embeds:
                vectors.extend(embeds)
                if isinstance(usage, dict) and usage.get("total_tokens"):
                    usage_tokens_total += int(usage.get("total_tokens") or 0)
                if size < len(texts):
                    # process remaining texts in the batch
                    rest = texts[size:]
                    for j in range(0, len(rest), 1):
                        embeds2, err2, _usage2 = create_embeddings(api_base, token, model, [rest[j]])
                        if err2 and "401" in err2:
                            token, err3 = get_valid_gigachat_access_token(db, force_refresh=True)
                            if token and not err3:
                                embeds2, err2, _usage2 = create_embeddings(api_base, token, model, [rest[j]])
                        if err2 and "429" in err2:
                            err = "rate_limited"
                            break
                        if err2 or not embeds2:
                            err = err2 or "embedding_failed"
                            break
                        vectors.extend(embeds2)
                        if isinstance(_usage2, dict) and _usage2.get("total_tokens"):
                            usage_tokens_total += int(_usage2.get("total_tokens") or 0)
                break
        if err:
            if "429" in str(err) or err == "rate_limited":
                rec.status = "queued"
                rec.error_message = "rate_limited"
                db.add(rec)
                db.commit()
                return {"ok": False, "error": "rate_limited"}
            rec.status = "error"
            rec.error_message = err or "embedding_failed"
            db.add(rec)
            db.commit()
            return {"ok": False, "error": rec.error_message}

    emb_rows: list[KBEmbedding] = []
    for ch, vec in zip(chunk_rows, vectors):
        emb_rows.append(KBEmbedding(
            chunk_id=ch.id,
            vector_json=vec,
            model=model,
            dim=len(vec) if vec else None,
            created_at=datetime.utcnow(),
        ))
    db.add_all(emb_rows)
    # record embedding usage (portal-level, no user)
    try:
        pricing = get_pricing(db)
        usage_tokens = usage_tokens_total if usage_tokens_total > 0 else None
        cost = calc_cost_rub(usage_tokens, pricing.get("embed_rub_per_1k", 0.0))
        record_usage(
            db,
            portal_id=rec.portal_id,
            user_id=None,
            request_id=f"file:{rec.id}",
            kind="embedding",
            model=model,
            tokens_prompt=None,
            tokens_completion=None,
            tokens_total=int(usage_tokens) if usage_tokens else None,
            cost_rub=cost,
            status="ok",
            error_code=None,
        )
    except Exception:
        pass
    rec.status = "ready"
    rec.processed_at = datetime.utcnow()
    db.add(rec)
    db.commit()
    return {"ok": True, "chunks": len(chunk_rows)}
