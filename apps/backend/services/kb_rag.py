"""RAG ответ по базе знаний портала."""
from __future__ import annotations

import math
import re
import json
from typing import Iterable, Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from apps.backend.models.kb import KBChunk, KBEmbedding, KBFile, KBSource
from apps.backend.models.dialog import Message
from apps.backend.models.dialog_rag_cache import DialogRagCache
from apps.backend.services.kb_settings import get_effective_gigachat_settings, get_valid_gigachat_access_token
from apps.backend.services.gigachat_client import create_embeddings, chat_complete
from apps.backend.services.kb_pgvector import query_top_chunks_by_pgvector

try:
    import pymorphy3  # type: ignore
except Exception:  # pragma: no cover - optional
    pymorphy3 = None

_MORPH = pymorphy3.MorphAnalyzer() if pymorphy3 else None

def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return -1.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _build_context(chunks: list[dict[str, Any]], max_chars: int = 4000) -> tuple[str, list[dict[str, Any]]]:
    parts: list[str] = []
    total = 0
    used: list[dict[str, Any]] = []
    for c in chunks:
        text = (c.get("text") or "").strip()
        if not text:
            continue
        if total + len(text) > max_chars:
            remaining = max_chars - total
            if remaining <= 0:
                break
            parts.append(text[:remaining])
            total += remaining
            used.append({**c, "text": text[:remaining]})
            break
        parts.append(text)
        total += len(text)
        used.append(c)
    return "\n\n".join(parts), used


def _format_citations(chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return ""
    lines = []
    for i, ch in enumerate(chunks, start=1):
        fname = ch.get("filename") or "Файл"
        cidx = ch.get("chunk_index")
        start_ms = ch.get("start_ms")
        end_ms = ch.get("end_ms")
        page_num = ch.get("page_num")
        ts = ""
        if isinstance(start_ms, int) and isinstance(end_ms, int):
            def _fmt(ms: int) -> str:
                s = max(0, int(ms / 1000))
                m = s // 60
                s = s % 60
                return f"{m:02d}:{s:02d}"
            ts = f", таймкод {_fmt(start_ms)}-{_fmt(end_ms)}"
        page = f", стр. {int(page_num)}" if isinstance(page_num, int) and page_num > 0 else ""
        quote = (ch.get("text") or "").replace("\n", " ").strip()
        if len(quote) > 240:
            quote = quote[:240].rstrip() + "…"
        frag = f"{fname}" if cidx is None else f"{fname}, фрагмент {int(cidx) + 1}"
        lines.append(f"Источник {i}: {frag}{page}{ts}. Цитата: {quote}")
    return "\n".join(lines)


def _format_citations_short(chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return ""
    seen = set()
    names: list[str] = []
    for ch in chunks:
        fname = (ch.get("filename") or "Файл").strip()
        if not fname:
            continue
        key = fname.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(fname)
    return ", ".join(names)


def _trigger_mode(text: str) -> str | None:
    t = (text or "").strip().lower()
    if not t:
        return None
    if t.startswith("сформировать") and "обзор" in t:
        return "summary"
    if "faq" in t or "вопросы и ответы" in t or "частые вопросы" in t:
        return "faq"
    if "таймлайн" in t or "хронолог" in t or "хронология" in t:
        return "timeline"
    return None


def _is_greeting(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    greetings = ("привет", "здравств", "добрый", "hello", "hi", "доброе утро", "добрый день", "добрый вечер")
    return any(t.startswith(g) for g in greetings) and len(t) <= 20


def _strip_markdown_basic(text: str) -> str:
    if not text:
        return text
    out = text
    out = out.replace("**", "").replace("__", "")
    out = re.sub(r"^\s{0,3}#{1,6}\s*", "", out, flags=re.M)
    out = out.replace("`", "")
    return out.strip()

_RU_STOPWORDS = {
    "и", "или", "а", "но", "что", "это", "как", "когда", "где", "зачем", "почему",
    "ли", "же", "бы", "быть", "есть", "нет", "про", "для", "при", "по", "об", "о",
    "на", "в", "из", "к", "до", "после", "над", "под", "между", "без", "с", "со",
    "так", "такой", "такие", "этот", "эта", "эти", "тот", "та", "те", "его", "ее",
    "их", "мы", "вы", "они", "я", "ты", "он", "она", "оно", "бывает", "нужно",
    "можно", "нельзя", "надо", "все", "всё", "вся", "всех",
}


def _extract_keywords(text: str) -> list[str]:
    t = (text or "").lower()
    if not t:
        return []
    words = re.findall(r"[a-zа-я0-9\-]{4,}", t, flags=re.IGNORECASE)
    out: list[str] = []
    for w in words:
        w = w.lower()
        if w.isdigit():
            continue
        if w in _RU_STOPWORDS:
            continue
        if _MORPH and re.fullmatch(r"[а-яё\-]+", w, flags=re.IGNORECASE):
            try:
                w = _MORPH.parse(w)[0].normal_form
            except Exception:
                pass
        out.append(w)
    # uniq while preserving order
    seen = set()
    uniq = []
    for w in out:
        if w in seen:
            continue
        seen.add(w)
        uniq.append(w)
    return uniq


def _is_follow_up(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    markers = (
        "выше", "подробнее", "собери", "всё", "все", "продолжи", "как ты писал",
        "ты же", "ранее", "в прошлом", "уточни", "расшифруй", "приведи",
    )
    return any(m in t for m in markers) or len(t) <= 8


def _load_dialog_history(db: Session, dialog_id: int, limit: int = 6) -> str:
    rows = db.execute(
        select(Message.direction, Message.body)
        .where(Message.dialog_id == dialog_id)
        .order_by(Message.id.desc())
        .limit(limit)
    ).all()
    if not rows:
        return ""
    lines = []
    for direction, body in reversed(rows):
        role = "Пользователь" if direction == "rx" else "Ассистент"
        text = (body or "").strip()
        if not text:
            continue
        lines.append(f"{role}: {text}")
    return "\n".join(lines)


def _load_rag_cache(db: Session, dialog_id: int, model: str) -> tuple[list[int], list[str]]:
    row = db.execute(
        select(DialogRagCache).where(
            DialogRagCache.dialog_id == dialog_id,
            DialogRagCache.model == model,
        )
    ).scalar_one_or_none()
    if not row:
        return [], []
    chunk_ids = []
    keywords = []
    try:
        chunk_ids = json.loads(row.chunk_ids_json or "[]")
    except Exception:
        chunk_ids = []
    try:
        keywords = json.loads(row.keywords_json or "[]")
    except Exception:
        keywords = []
    return [int(x) for x in chunk_ids if isinstance(x, (int, str)) and str(x).isdigit()], [str(x) for x in keywords]


def _save_rag_cache(db: Session, dialog_id: int, portal_id: int, model: str, chunk_ids: list[int], keywords: list[str]) -> None:
    row = db.execute(
        select(DialogRagCache).where(
            DialogRagCache.dialog_id == dialog_id,
            DialogRagCache.model == model,
        )
    ).scalar_one_or_none()
    if not row:
        row = DialogRagCache(dialog_id=dialog_id, portal_id=portal_id, model=model)
        db.add(row)
    row.chunk_ids_json = json.dumps(chunk_ids[:10], ensure_ascii=False)
    row.keywords_json = json.dumps(keywords[:20], ensure_ascii=False)
    db.commit()


def answer_from_kb(
    db: Session,
    portal_id: int,
    query: str,
    dialog_id: int | None = None,
    *,
    audience: str = "staff",
    system_prompt_extra_override: str | None = None,
    model_overrides: dict | None = None,
) -> tuple[str | None, str | None, dict | None]:
    query = (query or "").strip()
    if not query:
        return None, "empty_query", None
    if _is_greeting(query):
        return "Привет! Чем могу помочь по вашей базе знаний?", None, None
    mode = _trigger_mode(query)
    settings = get_effective_gigachat_settings(db, portal_id)
    preset = (settings.get("prompt_preset") or "").strip().lower()
    if preset and preset != "auto":
        mode = preset
    embed_model = (settings.get("embedding_model") or settings.get("model") or "").strip()
    chat_model = (settings.get("chat_model") or "").strip()
    api_base = (settings.get("api_base") or "").strip()
    temperature = float(settings.get("temperature") or 0.2)
    max_tokens = int(settings.get("max_tokens") or 700)
    top_p = settings.get("top_p")
    presence_penalty = settings.get("presence_penalty")
    frequency_penalty = settings.get("frequency_penalty")
    allow_general = bool(settings.get("allow_general")) if settings.get("allow_general") is not None else False
    strict_mode = bool(settings.get("strict_mode")) if settings.get("strict_mode") is not None else True
    context_messages = int(settings.get("context_messages") or 6)
    context_chars = int(settings.get("context_chars") or 4000)
    retrieval_top_k = int(settings.get("retrieval_top_k") or 5)
    retrieval_max_chars = int(settings.get("retrieval_max_chars") or 4000)
    lex_boost = float(settings.get("lex_boost") or 0.12)
    use_history = bool(settings.get("use_history")) if settings.get("use_history") is not None else True
    use_cache = bool(settings.get("use_cache")) if settings.get("use_cache") is not None else True
    system_prompt_extra = (settings.get("system_prompt_extra") or "").strip()
    show_sources = bool(settings.get("show_sources")) if settings.get("show_sources") is not None else True
    sources_format = (settings.get("sources_format") or "detailed").strip().lower()
    if system_prompt_extra_override:
        system_prompt_extra = (system_prompt_extra + " " + system_prompt_extra_override).strip() if system_prompt_extra else system_prompt_extra_override.strip()
    overrides = model_overrides or {}
    if overrides.get("embedding_model"):
        embed_model = str(overrides.get("embedding_model") or "").strip()
    if overrides.get("chat_model"):
        chat_model = str(overrides.get("chat_model") or "").strip()
    if overrides.get("api_base"):
        api_base = str(overrides.get("api_base") or "").strip()
    if overrides.get("temperature") is not None:
        try:
            temperature = float(overrides.get("temperature"))
        except Exception:
            pass
    if overrides.get("max_tokens") is not None:
        try:
            max_tokens = int(overrides.get("max_tokens"))
        except Exception:
            pass
    if overrides.get("top_p") is not None:
        top_p = overrides.get("top_p")
    if overrides.get("presence_penalty") is not None:
        presence_penalty = overrides.get("presence_penalty")
    if overrides.get("frequency_penalty") is not None:
        frequency_penalty = overrides.get("frequency_penalty")
    if overrides.get("system_prompt_extra"):
        extra_override = str(overrides.get("system_prompt_extra") or "").strip()
        if extra_override:
            system_prompt_extra = (system_prompt_extra + " " + extra_override).strip() if system_prompt_extra else extra_override
    if overrides.get("show_sources") is not None:
        show_sources = bool(overrides.get("show_sources"))
    if overrides.get("sources_format") is not None:
        sources_format = str(overrides.get("sources_format") or "none").strip().lower()
    import logging
    logging.getLogger(__name__).warning(
        "kb_rag_models portal_id=%s embed=%s chat=%s api_base=%s",
        portal_id,
        embed_model,
        chat_model,
        api_base,
    )
    if not embed_model:
        return None, "missing_embedding_model", None
    if not chat_model:
        return None, "missing_chat_model", None
    token, err = get_valid_gigachat_access_token(db)
    if err or not token:
        return None, err or "missing_access_token", None

    follow_up = _is_follow_up(query)
    cached_chunk_ids: list[int] = []
    cached_keywords: list[str] = []
    if dialog_id:
        cached_chunk_ids, cached_keywords = _load_rag_cache(db, dialog_id, embed_model)
    query_for_embed = query
    if follow_up and cached_keywords:
        query_for_embed = query + " " + " ".join(cached_keywords[:5])
    q_vecs, err, _usage = create_embeddings(api_base, token, embed_model, [query_for_embed])
    if err or not q_vecs:
        return None, err or "embedding_failed", None
    qv = q_vecs[0]

    aud = audience if audience in ("staff", "client") else "staff"
    pg_rows = query_top_chunks_by_pgvector(
        db,
        portal_id=portal_id,
        audience=aud,
        model=embed_model,
        query_vec=qv,
        limit=max(50, retrieval_top_k * 6),
    )

    scored: list[tuple[float, bool, dict[str, Any]]] = []
    if pg_rows:
        keywords = _extract_keywords(query)
        for r in pg_rows:
            txt = (r.get("text") or "")
            txt_low = txt.lower()
            lex_match = any(k in txt_low for k in keywords) if keywords else False
            score = float(r.get("score") or 0.0)
            if lex_match:
                score += lex_boost
            scored.append(
                (
                    score,
                    lex_match,
                    {
                        "text": txt,
                        "chunk_index": r.get("chunk_index"),
                        "start_ms": r.get("start_ms"),
                        "end_ms": r.get("end_ms"),
                        "page_num": r.get("page_num"),
                        "filename": r.get("filename") or "",
                        "mime_type": r.get("mime_type") or "",
                        "chunk_id": r.get("chunk_id"),
                        "file_id": r.get("file_id"),
                        "source_type": r.get("source_type") or "",
                        "source_url": r.get("source_url") or "",
                    },
                )
            )
    else:
        base_query = (
            select(
                KBEmbedding.vector_json,
                KBChunk.text,
                KBChunk.chunk_index,
                KBChunk.start_ms,
                KBChunk.end_ms,
                KBChunk.page_num,
                KBFile.filename,
                KBFile.mime_type,
                KBChunk.id,
                KBFile.id,
                KBSource.source_type,
                KBSource.url,
            )
            .join(KBChunk, KBChunk.id == KBEmbedding.chunk_id)
            .join(KBFile, KBFile.id == KBChunk.file_id)
            .join(KBSource, KBSource.id == KBFile.source_id, isouter=True)
            .where(
                KBChunk.portal_id == portal_id,
                KBFile.status == "ready",
                KBFile.audience == aud,
            )
            .order_by(KBChunk.id.desc())
            .limit(2000)
        )
        rows = db.execute(
            base_query.where(KBEmbedding.model == embed_model)
        ).all()
        if not rows:
            rows = db.execute(
                base_query.where(KBEmbedding.model.is_(None))
            ).all()
        if not rows:
            return None, "kb_empty", None

        keywords = _extract_keywords(query)
        for vec, text, chunk_index, start_ms, end_ms, page_num, filename, mime_type, chunk_id, file_id, source_type, source_url in rows:
            if not isinstance(vec, list):
                continue
            txt = (text or "")
            txt_low = txt.lower()
            lex_match = any(k in txt_low for k in keywords) if keywords else False
            score = _cosine(qv, vec)
            if lex_match:
                score += lex_boost
            scored.append((
                score,
                lex_match,
                {
                    "text": txt,
                    "chunk_index": chunk_index,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "page_num": page_num,
                    "filename": filename or "",
                    "mime_type": mime_type or "",
                    "chunk_id": chunk_id,
                    "file_id": file_id,
                    "source_type": source_type or "",
                    "source_url": source_url or "",
                }
            ))
    if not scored:
        return None, "kb_empty", None
    scored.sort(key=lambda x: x[0], reverse=True)
    top_k = retrieval_top_k
    max_chars = retrieval_max_chars
    if "собери" in query.lower() or "всю информацию" in query.lower():
        top_k = max(8, retrieval_top_k)
        max_chars = max(6000, retrieval_max_chars)
    if keywords:
        lex = [t for _s, is_lex, t in scored if is_lex][: min(3, top_k)]
        sem = [t for _s, _is_lex, t in scored if t not in lex][: max(0, top_k - len(lex))]
        top_chunks = lex + sem
    else:
        top_chunks = [t for _s, _is_lex, t in scored[:top_k]]
    if follow_up and cached_chunk_ids and use_cache:
        cached = [t for _s, _is_lex, t in scored if t.get("chunk_id") in cached_chunk_ids]
        top_chunks = (cached + top_chunks)[:top_k]
    context, used_chunks = _build_context(top_chunks, max_chars=max_chars)
    if not context:
        if allow_general and not strict_mode:
            system_text = (
                "Ты полезный ассистент. Отвечай живым человеческим языком. "
                "Формат: простой текст, без Markdown, без ** и ###."
            )
            if system_prompt_extra:
                system_text += " " + system_prompt_extra
            messages = [
                {"role": "system", "content": system_text},
                {"role": "user", "content": query},
            ]
            answer, err, usage = chat_complete(
                api_base,
                token,
                chat_model,
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
            )
            if err or not answer:
                return None, err or "empty_answer", usage
            out = _strip_markdown_basic(answer.strip())
            out = re.sub(r"\[\d+\]", "", out).strip()
            return out, None, usage
        return None, "kb_empty", None
    numbered_context = "\n\n".join(
        [f"[{i+1}] {c.get('text','')}" for i, c in enumerate(used_chunks)]
    )

    system_text = (
        "Ты помощник базы знаний компании. Отвечай только по контексту. "
        "Пиши живым человеческим языком, добавляй объясняющие выводы. "
        "Формат: простой текст, без Markdown, без ** и ###. "
        "Если нужны шаги — используй нумерацию 1), 2), 3) в одну строку. "
        "Ссылки на источники не встраивай в текст, а вынеси отдельным блоком 'Источники:' в конце."
    )
    if sources_format in ("none", "off", "false") or not show_sources:
        system_text += " Не упоминай источники, книги, внешние базы и названия документов в ответе."
    if system_prompt_extra:
        system_text += " " + system_prompt_extra
    if mode == "summary":
        system_text += " Сформируй краткий обзор."
    elif mode == "faq":
        system_text += " Сформируй FAQ: 5-10 вопросов и ответы."
    elif mode == "timeline":
        system_text += " Сформируй таймлайн (хронологию) по контексту."
    history = _load_dialog_history(db, dialog_id, limit=context_messages) if (dialog_id and use_history) else ""
    if history and follow_up and use_history:
        user_content = f"История диалога:\n{history}\n\nКонтекст:\n{numbered_context}\n\nЗапрос: {query}\nОтвет:"
    else:
        user_content = f"Контекст:\n{numbered_context}\n\nЗапрос: {query}\nОтвет:"
    messages = [
        {"role": "system", "content": system_text},
        {"role": "user", "content": user_content},
    ]
    answer, err, usage = chat_complete(
        api_base,
        token,
        chat_model,
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
    )
    if err and "401" in err:
        token, err2 = get_valid_gigachat_access_token(db, force_refresh=True)
        if token and not err2:
            answer, err, usage = chat_complete(
                api_base,
                token,
                chat_model,
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
            )
    if isinstance(usage, dict):
        usage["model"] = chat_model
    if err or not answer:
        return None, err or "empty_answer", usage
    out = _strip_markdown_basic(answer.strip())
    out = re.sub(r"\[\d+\]", "", out).strip()
    if show_sources and sources_format not in ("none", "off", "false"):
        if sources_format == "short":
            short_list = _format_citations_short(used_chunks)
            if short_list:
                out = out + "\n\nИсточники: " + short_list
        else:
            citations = _format_citations(used_chunks)
            if citations:
                out = out + "\n\nИсточники:\n" + citations
    source_items = [
        {
            "file_id": int(c.get("file_id")) if c.get("file_id") is not None else None,
            "chunk_id": int(c.get("chunk_id")) if c.get("chunk_id") is not None else None,
            "filename": c.get("filename") or "",
            "mime_type": c.get("mime_type") or "",
            "source_type": c.get("source_type") or "",
            "source_url": c.get("source_url") or "",
            "chunk_index": c.get("chunk_index"),
            "start_ms": c.get("start_ms"),
            "end_ms": c.get("end_ms"),
            "page_num": c.get("page_num"),
            "text": c.get("text") or "",
        }
        for c in used_chunks
    ]
    if usage is None:
        usage = {}
    if isinstance(usage, dict):
        usage["sources"] = source_items
    if dialog_id and use_cache:
        used_ids = [int(c.get("chunk_id")) for c in used_chunks if c.get("chunk_id")]
        _save_rag_cache(db, dialog_id, portal_id, embed_model, used_ids, keywords)
    file_ids = {int(c.get("file_id")) for c in used_chunks if c.get("file_id")}
    if file_ids:
        db.execute(
            update(KBFile)
            .where(KBFile.id.in_(file_ids))
            .values(query_count=KBFile.query_count + 1)
        )
        db.commit()
    return out, None, usage
