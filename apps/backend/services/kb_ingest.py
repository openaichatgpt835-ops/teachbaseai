"""KB ingestion: parse files, chunk text, generate embeddings."""
from __future__ import annotations

import csv
import hashlib
import json
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
from apps.backend.services.kb_pgvector import write_vector_column
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


_VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
_MEDIA_CHUNK_SECONDS = max(60, int(os.getenv("MEDIA_CHUNK_SECONDS") or 600))
_MEDIA_CHUNK_OVERLAP_SECONDS = max(0, int(os.getenv("MEDIA_CHUNK_OVERLAP_SECONDS") or 2))

_CHUNK_PROFILES: dict[str, tuple[int, int]] = {
    # default narrative text
    "default": (1200, 200),
    # tables/spreadsheets/rows
    "tabular": (700, 120),
    # scanned/ocr pages benefit from shorter windows
    "ocr": (900, 140),
    # media transcript chunks
    "media": (1000, 120),
}


def _chunk_profile_for_ext(ext: str) -> tuple[int, int]:
    ext = (ext or "").lower()
    if ext in (".csv", ".xls", ".xlsx"):
        return _CHUNK_PROFILES["tabular"]
    if ext in (".png", ".jpg", ".jpeg"):
        return _CHUNK_PROFILES["ocr"]
    if ext in _VIDEO_EXTS:
        return _CHUNK_PROFILES["media"]
    return _CHUNK_PROFILES["default"]


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


def _media_duration_seconds(src_path: str) -> int:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        src_path,
    ]
    out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8", errors="ignore").strip()
    try:
        return max(1, int(float(out)))
    except Exception:
        return 1


_WHISPER_MODEL = None


def _get_whisper_model():
    global _WHISPER_MODEL
    if _WHISPER_MODEL is not None:
        return _WHISPER_MODEL
    from faster_whisper import WhisperModel  # type: ignore
    size = (os.getenv("WHISPER_MODEL_SIZE") or "small").strip()
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


def _transcribe_media_window(path: str, start_sec: int, duration_sec: int) -> list[_Segment]:
    with tempfile.TemporaryDirectory() as td:
        chunk_wav = os.path.join(td, "chunk.wav")
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(max(0, start_sec)),
            "-i",
            path,
            "-t",
            str(max(1, duration_sec)),
            "-ac",
            "1",
            "-ar",
            "16000",
            chunk_wav,
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return _transcribe_media(chunk_wav)


def _read_transcript_segments_jsonl(path: str) -> list[_Segment]:
    if not os.path.exists(path):
        return []
    out: list[_Segment] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                txt = str(row.get("text") or "").strip()
                if not txt:
                    continue
                out.append(
                    _Segment(
                        text=txt,
                        start_ms=int(row.get("start_ms") or 0),
                        end_ms=int(row.get("end_ms") or 0),
                    )
                )
            except Exception:
                continue
    return out


def _append_transcript_segment_jsonl(path: str, seg: _Segment) -> None:
    row = {"start_ms": seg.start_ms, "end_ms": seg.end_ms, "text": seg.text}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _transcribe_media_resumable(
    src_path: str,
    transcript_jsonl_path: str,
    progress_cb=None,
) -> list[_Segment]:
    segments = _read_transcript_segments_jsonl(transcript_jsonl_path)
    last_end_ms = segments[-1].end_ms if segments else 0
    total_sec = _media_duration_seconds(src_path)
    overlap_ms = _MEDIA_CHUNK_OVERLAP_SECONDS * 1000
    start_sec = max(0, int(max(0, last_end_ms - overlap_ms) / 1000))
    if start_sec >= total_sec:
        if progress_cb:
            progress_cb(100)
        return segments

    pos = start_sec
    while pos < total_sec:
        win = min(_MEDIA_CHUNK_SECONDS, total_sec - pos)
        win_segments = _transcribe_media_window(src_path, pos, win)
        for seg in win_segments:
            shifted = _Segment(
                text=seg.text,
                start_ms=seg.start_ms + pos * 1000,
                end_ms=seg.end_ms + pos * 1000,
            )
            # Skip overlap duplicates on resume/chunk boundaries.
            if shifted.end_ms <= last_end_ms:
                continue
            segments.append(shifted)
            _append_transcript_segment_jsonl(transcript_jsonl_path, shifted)
            last_end_ms = max(last_end_ms, shifted.end_ms)
        pos += max(1, _MEDIA_CHUNK_SECONDS - _MEDIA_CHUNK_OVERLAP_SECONDS)
        if progress_cb and total_sec > 0:
            progress_cb(min(99, int((min(pos, total_sec) / total_sec) * 100)))

    if progress_cb:
        progress_cb(100)
    return segments


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
        max_chars, overlap = _chunk_profile_for_ext(ext)
        ocr_enabled = (os.getenv("OCR_ENABLED") or "").strip().lower() in ("1", "true", "yes", "on")
        if ext in _VIDEO_EXTS:
            try:
                transcript_jsonl_path = rec.storage_path + ".transcript.jsonl"

                def _set_progress(pct: int) -> None:
                    rec.error_message = f"transcribe_progress:{max(0, min(100, int(pct)))}"
                    db.add(rec)
                    db.commit()

                with tempfile.TemporaryDirectory() as td:
                    wav_path = os.path.join(td, "audio.wav")
                    _extract_audio_to_wav(rec.storage_path, wav_path)
                    segments = _transcribe_media_resumable(
                        wav_path,
                        transcript_jsonl_path=transcript_jsonl_path,
                        progress_cb=_set_progress,
                    )
                chunks = _chunk_segments(segments, max_chars=max_chars)
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
                        chunks.extend(chunk_text_with_page(page_text, page_num, max_chars=max_chars, overlap=overlap))
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
                chunks = chunk_text(text, max_chars=max_chars, overlap=overlap)

        if not chunks and ext == ".pdf":
            if ocr_enabled:
                try:
                    text = _ocr_pdf_file(rec.storage_path)
                    chunks = chunk_text(text, max_chars=max_chars, overlap=overlap)
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
                audience=rec.audience or "staff",
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

    def _unpack_embeddings(result):
        if isinstance(result, tuple):
            if len(result) == 3:
                return result
            if len(result) == 2:
                embeds, err = result
                return embeds, err, None
        return None, "invalid_embeddings_response", None

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
            embeds, err, usage = _unpack_embeddings(create_embeddings(api_base, token, model, subset))
            if err and "401" in err:
                token, err2 = get_valid_gigachat_access_token(db, force_refresh=True)
                if token and not err2:
                    embeds, err, usage = _unpack_embeddings(create_embeddings(api_base, token, model, subset))
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
                        embeds2, err2, _usage2 = _unpack_embeddings(create_embeddings(api_base, token, model, [rest[j]]))
                        if err2 and "401" in err2:
                            token, err3 = get_valid_gigachat_access_token(db, force_refresh=True)
                            if token and not err3:
                                embeds2, err2, _usage2 = _unpack_embeddings(create_embeddings(api_base, token, model, [rest[j]]))
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
    db.flush()
    for emb_row, vec in zip(emb_rows, vectors):
        if emb_row.id:
            write_vector_column(db, int(emb_row.id), vec)
    db.commit()
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
    rec.error_message = None
    rec.processed_at = datetime.utcnow()
    db.add(rec)
    db.commit()
    return {"ok": True, "chunks": len(chunk_rows)}
