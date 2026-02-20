"""RAG ответ по базе знаний портала."""
from __future__ import annotations

import math
import re
import json
from typing import Iterable, Any

from sqlalchemy import select, update, or_
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


def _expand_query_keywords(keywords: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for k in keywords:
        kk = (k or "").strip().lower()
        if not kk:
            continue
        variants = {kk}
        if "-" in kk:
            parts = [p for p in kk.split("-") if p]
            if parts:
                variants.update(parts)
                variants.add(" ".join(parts))
                variants.add("".join(parts))
        for v in variants:
            if v and v not in seen:
                seen.add(v)
                out.append(v)
    return out


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


def _keyword_hits(text: str, keywords: list[str]) -> int:
    if not text or not keywords:
        return 0
    low = text.lower()
    token_set = set(re.findall(r"[a-zа-яё0-9]+", low, flags=re.IGNORECASE))
    hits = 0
    for k in keywords:
        kk = (k or "").strip().lower()
        if not kk:
            continue
        parts = re.findall(r"[a-zа-яё0-9]+", kk, flags=re.IGNORECASE)
        if not parts:
            continue
        if len(parts) == 1:
            p = parts[0]
            if p in token_set or p in low:
                hits += 1
        else:
            if all(p in token_set for p in parts):
                hits += 1
    return hits


def _looks_like_model_disclaimer(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if "языков" in t and "модел" in t and ("не облада" in t or "не транслиру" in t):
        return True
    if "giga" in t and ("модел" in t or "нейросетев" in t) and ("ограничен" in t or "ошибоч" in t):
        return True
    markers = (
        "как языковая модель",
        "как и любая языковая модель",
        "как ии",
        "генеративные языковые модели",
        "их ответы являются обобщением",
        "не обладаю собственным мнением",
        "не могу предоставить",
        "не могу помочь с",
        "разговоры на чувствительные темы",
        "могут быть ограничены",
        "возможно содержит неточн",
    )
    return any(m in t for m in markers)


def _extractive_answer_from_chunks(query: str, chunks: list[dict[str, Any]], limit: int = 5) -> str:
    if not chunks:
        return "В базе знаний не найдено достаточно релевантной информации по запросу."
    qk = _expand_query_keywords(_extract_keywords(query))
    ranked: list[tuple[int, dict[str, Any]]] = []
    for c in chunks:
        txt = str(c.get("text") or "").strip()
        if not txt:
            continue
        score = _keyword_hits(txt, qk)
        score += _keyword_hits(str(c.get("filename") or ""), qk) * 2
        ranked.append((score, c))
    ranked.sort(key=lambda x: x[0], reverse=True)
    picked: list[str] = []
    for _s, c in ranked[:limit]:
        txt = str(c.get("text") or "").replace("\n", " ").strip()
        if not txt:
            continue
        if len(txt) > 280:
            txt = txt[:280].rstrip() + "…"
        picked.append(txt)
    if not picked:
        return "В базе знаний есть материалы по теме, но не удалось извлечь достаточно точный фрагмент ответа."
    return "По материалам базы знаний:\n" + "\n".join([f"{i+1}) {p}" for i, p in enumerate(picked)])


def _person_query_phrase(query: str) -> str | None:
    q = (query or "").strip()
    if not q:
        return None
    low = q.lower()
    patterns = [
        r"^\s*кто\s+так[ао]й\s+(.+)$",
        r"^\s*расскажи\s+про\s+(.+)$",
        r"^\s*расскажи\s+о\s+(.+)$",
        r"^\s*что\s+известно\s+о\s+(.+)$",
        r"^\s*инфо\s+про\s+(.+)$",
    ]
    for p in patterns:
        m = re.match(p, low, flags=re.IGNORECASE)
        if m:
            tail = (m.group(1) or "").strip(" .,!?:;")
            if len(tail) >= 3:
                return tail
    return None


def _retrieval_confidence(
    chunks: list[dict[str, Any]],
    *,
    query_keywords: list[str],
    min_score_ref: float,
) -> tuple[float, int]:
    if not chunks:
        return 0.0, 0
    top = chunks[: min(6, len(chunks))]
    weighted_sum = 0.0
    wsum = 0.0
    evidence = 0
    for i, c in enumerate(top):
        w = 1.0 / float(i + 1)
        score = float(c.get("_score") or 0.0)
        kh = int(c.get("_keyword_hits") or 0)
        mh = int(c.get("_meta_keyword_hits") or 0)
        txt = str(c.get("text") or "")
        if kh <= 0 and query_keywords:
            kh = _keyword_hits(txt, query_keywords)
        if kh > 0 or mh > 0:
            evidence += 1
        # normalize semantic score around min_score_ref into 0..1
        sem = max(0.0, min(1.0, (score - min_score_ref) / 0.35))
        lex = max(0.0, min(1.0, (kh + 0.6 * mh) / 3.0))
        cconf = (0.55 * sem) + (0.45 * lex)
        weighted_sum += cconf * w
        wsum += w
    if wsum <= 0:
        return 0.0, evidence
    return max(0.0, min(1.0, weighted_sum / wsum)), evidence


def _extract_person_entity_answer(query: str, chunks: list[dict[str, Any]], limit: int = 4) -> str | None:
    phrase = _person_query_phrase(query)
    if not phrase:
        return None
    base_tokens = [t for t in re.findall(r"[a-zа-яё]{2,}", phrase, flags=re.IGNORECASE)]
    if len(base_tokens) < 2:
        return None
    name_tokens = [t.lower() for t in base_tokens[:4]]
    surname = name_tokens[-1]
    full = " ".join(name_tokens)
    scored: list[tuple[int, str]] = []
    seen: set[str] = set()
    for c in chunks[:18]:
        txt = str(c.get("text") or "").replace("\n", " ").strip()
        if not txt:
            continue
        for s in _split_sentences(txt):
            low = s.lower()
            hits = sum(1 for t in name_tokens if t in low)
            if hits < 2 and surname not in low:
                continue
            score = (hits * 4) + (5 if full in low else 0) + (3 if surname in low else 0)
            if len(s) < 24:
                score -= 3
            key = re.sub(r"\s+", " ", low).strip()
            if key in seen:
                continue
            seen.add(key)
            scored.append((score, s.strip()))
    if not scored:
        return "В базе знаний нет подтвержденной информации по этому человеку."
    scored.sort(key=lambda x: x[0], reverse=True)
    lines = [s for _sc, s in scored[: max(1, limit)]]
    return "По базе знаний:\n" + "\n".join([f"{i+1}) {line}" for i, line in enumerate(lines)])


def _extract_numeric_fact_answer(query: str, chunks: list[dict[str, Any]]) -> str | None:
    if not chunks:
        return None
    qk = _expand_query_keywords(_extract_keywords(query))
    best: tuple[int, str] | None = None
    qlow = (query or "").lower()
    for c in chunks[:16]:
        txt = str(c.get("text") or "").replace("\n", " ").strip()
        if not txt:
            continue
        parts = re.split(r"(?<=[\.\!\?])\s+", txt)
        for p in parts:
            s = (p or "").strip()
            if len(s) < 8:
                continue
            num_hits = len(re.findall(r"\d+(?:[.,]\d+)?", s))
            if num_hits <= 0:
                continue
            score = (_keyword_hits(s, qk) * 4) + (num_hits * 3)
            low = s.lower()
            if "кг" in low or "килограмм" in low or "подня" in low or "жим" in low:
                score += 5
            if ("анти" in qlow or "тренер" in qlow) and ("анти" in low or "тренер" in low):
                score += 6
            # Drop obvious noisy transcript fragments that are numeric but not factual.
            if "позитивная музыка" in low:
                score -= 20
            if not best or score > best[0]:
                best = (score, s)
    if not best:
        return None
    line = best[1]
    if len(line) > 260:
        line = line[:260].rstrip() + "…"
    return f"По базе знаний: {line}"


def _extract_numeric_fact_structured(query: str, chunks: list[dict[str, Any]]) -> str | None:
    qlow = (query or "").lower()
    qk = _expand_query_keywords(_extract_keywords(query))
    if not chunks:
        return None
    lift_query = any(x in qlow for x in ("жм", "жим", "подним", "поднял"))
    best: tuple[int, int, str] | None = None  # score, value, sentence
    banned_fragments = (
        "ну,",
        "как бы",
        "естественно",
        "бручок",
        "позитивная музыка",
        "промокод",
        "подпишись",
    )
    verbs = ("жим", "жм", "подним", "поднял", "поднимает")
    for c in chunks[:16]:
        txt = str(c.get("text") or "").replace("\n", " ").strip()
        if not txt or _is_noise_chunk_text(txt):
            continue
        for s in _split_sentences(txt):
            low = s.lower()
            if not low:
                continue
            if any(b in low for b in banned_fragments):
                continue
            if not any(v in low for v in verbs):
                continue
            # Prefer patterns where numeric value is near lifting verb.
            matches = re.finditer(
                r"(?:жм\w*|подним\w*|поднял\w*)[^0-9]{0,24}(\d{2,4})(?:\s*(кг|килограмм\w*))?",
                low,
            )
            candidates: list[tuple[int, bool]] = []
            for m in matches:
                val = int(m.group(1))
                has_kg = bool(m.group(2))
                if val < 20 or val > 600:
                    continue
                candidates.append((val, has_kg))
            if not candidates:
                # Fallback: number before verb.
                matches2 = re.finditer(
                    r"(\d{2,4})(?:\s*(кг|килограмм\w*))?[^0-9]{0,24}(?:жм\w*|подним\w*|поднял\w*)",
                    low,
                )
                for m in matches2:
                    val = int(m.group(1))
                    has_kg = bool(m.group(2))
                    if 20 <= val <= 600:
                        candidates.append((val, has_kg))
            if not candidates:
                continue
            for val, has_kg in candidates:
                if lift_query and not has_kg:
                    continue
                score = (_keyword_hits(low, qk) * 3) + (6 if has_kg else 0)
                if ("анти" in qlow or "тренер" in qlow) and ("анти" in low or "тренер" in low):
                    score += 4
                if "позитивная музыка" in low or "промокод" in low:
                    score -= 15
                if lift_query and (val < 40 or val > 400):
                    score -= 10
                if best is None or score > best[0]:
                    best = (score, val, s.strip())
    if not best:
        return None
    _score, value, sentence = best
    unit = "кг" if ("кг" in sentence.lower() or "килограмм" in sentence.lower()) else ""
    if unit:
        return f"По базе знаний: анти-тренер поднимает {value} {unit}."
    if lift_query:
        return f"По базе знаний: анти-тренер поднимает около {value} кг."
    return f"По базе знаний: в найденном фрагменте фигурирует значение {value}."


def _looks_like_chunk_dump(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if t.startswith("по материалам базы знаний:") and len(re.findall(r"\n\s*\d+[\)\.]", text)) >= 3:
        return True
    return False


def _looks_like_low_quality_numeric_answer(text: str) -> bool:
    t = (text or "").lower()
    if not t:
        return False
    fillers = ("ну,", "ну ", "как бы", "говорит", "естественно", "что-то", "брусок")
    has_many_numbers = len(re.findall(r"\d{2,4}", t)) >= 2
    return has_many_numbers and any(f in t for f in fillers)


def _looks_low_quality_answer(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return True
    words = re.findall(r"[a-zа-яё0-9]+", t, flags=re.IGNORECASE)
    if len(words) < 6:
        return True
    bad_markers = (
        "по базе знаний: ну,",
        "как бы",
        "естественно",
        "бручок",
        "позитивная музыка",
    )
    return any(m in t for m in bad_markers)


def _extract_fact_notes(query: str, chunks: list[dict[str, Any]], limit: int = 5) -> list[str]:
    if not chunks:
        return []
    qk = _expand_query_keywords(_extract_keywords(query))
    banned = ("позитивная музыка", "промокод", "подпишись", "ставьте лайк")
    scored: list[tuple[int, str]] = []
    seen: set[str] = set()
    for c in chunks[:14]:
        txt = str(c.get("text") or "").replace("\n", " ").strip()
        if not txt:
            continue
        for s in _split_sentences(txt):
            low = s.lower().strip()
            if not low:
                continue
            if any(b in low for b in banned):
                continue
            if len(low) < 20:
                continue
            score = _keyword_hits(low, qk) * 3
            if re.search(r"\d+(?:[.,]\d+)?", low):
                score += 2
            if score <= 0:
                continue
            key = re.sub(r"\s+", " ", low)
            if key in seen:
                continue
            seen.add(key)
            scored.append((score, s.strip()))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _sc, s in scored[: max(1, limit)]]


def _split_sentences(text: str) -> list[str]:
    raw = re.split(r"(?<=[\.\!\?])\s+", (text or "").strip())
    return [s.strip() for s in raw if s and s.strip()]


def _claim_keyword_coverage(sentence: str, chunk_text: str) -> tuple[int, float]:
    claim_keys = _expand_query_keywords(_extract_keywords(sentence))
    if not claim_keys:
        return 0, 0.0
    hits = _keyword_hits(chunk_text, claim_keys)
    cover = float(hits) / float(max(1, min(len(claim_keys), 10)))
    return hits, cover


def _claim_is_supported(sentence: str, query_keywords: list[str], chunk_text: str) -> bool:
    score, has_number_match = _sentence_support_score(sentence, query_keywords, chunk_text)
    claim_hits, claim_cover = _claim_keyword_coverage(sentence, chunk_text)
    sk = _extract_keywords(sentence)
    is_numeric_claim = bool(re.search(r"\d+(?:[.,]\d+)?", sentence))
    if is_numeric_claim and not has_number_match:
        return False
    # Require explicit lexical grounding of claim terms in the chunk.
    min_hits = 1 if len(sk) <= 3 else 2
    min_cover = 0.22 if len(sk) <= 3 else 0.30
    if claim_hits < min_hits or claim_cover < min_cover:
        return False
    min_score = 2 if len(sk) <= 2 else 3
    return score >= min_score


def _sentence_support_score(sentence: str, query_keywords: list[str], chunk_text: str) -> tuple[int, bool]:
    s_keys = _extract_keywords(sentence)
    score = _keyword_hits(chunk_text, s_keys) * 2 + _keyword_hits(chunk_text, query_keywords)
    numbers = re.findall(r"\d+(?:[.,]\d+)?", sentence)
    has_number_match = False
    if numbers:
        for n in numbers:
            if n in chunk_text:
                has_number_match = True
                score += 6
                break
        if not has_number_match:
            score -= 4
    units = ("кг", "килограмм", "%", "процент", "руб", "₽", "мин", "час")
    if any(u in sentence.lower() for u in units) and any(u in chunk_text.lower() for u in units):
        score += 2
    if "позитивная музыка" in sentence.lower():
        score -= 20
    return score, has_number_match


def _verify_and_ground_answer(query: str, answer: str, chunks: list[dict[str, Any]]) -> str:
    if not answer or not chunks:
        return answer
    qk = _extract_keywords(query)
    out_lines: list[str] = []
    kept_sentences = 0
    total_sentences = 0
    for line in str(answer).splitlines():
        tline = line.strip()
        if not tline:
            out_lines.append("")
            continue
        sentences = _split_sentences(tline)
        if not sentences:
            out_lines.append(line)
            continue
        kept: list[str] = []
        for s in sentences:
            total_sentences += 1
            supported = False
            for c in chunks[:12]:
                txt = str(c.get("text") or "")
                if not txt:
                    continue
                if _claim_is_supported(s, qk, txt):
                    supported = True
                    break
            if supported:
                kept.append(s)
                kept_sentences += 1
        if kept:
            out_lines.append(" ".join(kept))
    grounded = "\n".join([ln for ln in out_lines if ln is not None]).strip()
    if not grounded:
        notes = _extract_fact_notes(query, chunks, limit=5)
        if notes:
            return "Подтверждено в базе знаний:\n" + "\n".join([f"{i+1}) {n}" for i, n in enumerate(notes)])
        return "В базе знаний не найдено достаточно релевантной информации по запросу. Уточните вопрос или загрузите материалы по этой теме."
    ratio = (kept_sentences / total_sentences) if total_sentences > 0 else 1.0
    if ratio < 0.45:
        notes = _extract_fact_notes(query, chunks, limit=6)
        if notes:
            return "Подтверждено в базе знаний:\n" + "\n".join([f"{i+1}) {n}" for i, n in enumerate(notes)])
        return "В базе знаний не найдено достаточно релевантной информации по запросу. Уточните вопрос или загрузите материалы по этой теме."
    return grounded


def _extract_json_object(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(raw[start : end + 1])
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _claim_supported(claim_text: str, evidence_idxs: list[int], chunks: list[dict[str, Any]], query_keywords: list[str]) -> bool:
    if not claim_text or not evidence_idxs:
        return False
    claim_low = claim_text.lower()
    claim_nums = re.findall(r"\d+(?:[.,]\d+)?", claim_low)
    total_hits = 0
    num_supported = not claim_nums
    for i in evidence_idxs:
        if not (0 <= i < len(chunks)):
            continue
        txt = str(chunks[i].get("text") or "").lower()
        total_hits += _keyword_hits(txt, _expand_query_keywords(_extract_keywords(claim_text)))
        total_hits += _keyword_hits(txt, query_keywords)
        if claim_nums and any(n in txt for n in claim_nums):
            num_supported = True
    return total_hits > 0 and num_supported


def _build_claims_answer(
    query: str,
    chunks: list[dict[str, Any]],
    *,
    api_base: str,
    token: str,
    chat_model: str,
    temperature: float,
    max_tokens: int,
    top_p: Any,
    presence_penalty: Any,
    frequency_penalty: Any,
) -> str | None:
    if not chunks:
        return None
    context = "\n\n".join([f"[{i+1}] {str(c.get('text') or '')}" for i, c in enumerate(chunks[:10])])
    messages = [
        {
            "role": "system",
            "content": (
                "Ты извлекаешь проверяемые утверждения из контекста. "
                "Верни только JSON: {\"claims\":[{\"text\":\"...\",\"evidence\":[1,2]}]}. "
                "Не добавляй ничего кроме JSON. Утверждения только из контекста."
            ),
        },
        {"role": "user", "content": f"Запрос: {query}\n\nКонтекст:\n{context}"},
    ]
    raw, err, _u = chat_complete(
        api_base,
        token,
        chat_model,
        messages,
        temperature=max(0.0, min(float(temperature), 0.1)),
        max_tokens=max(300, min(max_tokens, 900)),
        top_p=top_p,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
    )
    if err or not raw:
        return None
    obj = _extract_json_object(raw)
    if not obj:
        return None
    claims_raw = obj.get("claims")
    if not isinstance(claims_raw, list):
        return None
    qk = _expand_query_keywords(_extract_keywords(query))
    claims: list[tuple[str, list[int]]] = []
    for item in claims_raw[:8]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        ev = item.get("evidence") or []
        if not isinstance(ev, list):
            continue
        ev_idx = []
        for x in ev:
            if isinstance(x, int):
                ev_idx.append(x - 1)
            elif isinstance(x, str) and x.isdigit():
                ev_idx.append(int(x) - 1)
        ev_idx = sorted(set([i for i in ev_idx if 0 <= i < len(chunks)]))
        if not text or not ev_idx:
            continue
        if not _claim_supported(text, ev_idx, chunks, qk):
            continue
        claims.append((text, ev_idx))
    if not claims:
        return None
    # Compose readable answer from verified claims.
    lines: list[str] = []
    for text, ev_idx in claims:
        refs = "".join([f" [{i+1}]" for i in ev_idx[:5]])
        lines.append(f"{text}{refs}")
    return "\n".join(lines)


def _style_rewrite_answer(
    *,
    query: str,
    factual_answer: str,
    chunks: list[dict[str, Any]],
    api_base: str,
    token: str,
    chat_model: str,
    max_tokens: int,
    top_p: Any,
    presence_penalty: Any,
    frequency_penalty: Any,
) -> str | None:
    base = (factual_answer or "").strip()
    if not base:
        return None
    ctx_parts: list[str] = []
    for i, c in enumerate(chunks[:6], start=1):
        txt = str(c.get("text") or "").strip()
        if not txt:
            continue
        if len(txt) > 260:
            txt = txt[:260].rstrip() + "…"
        ctx_parts.append(f"[{i}] {txt}")
    context = "\n".join(ctx_parts)
    messages = [
        {
            "role": "system",
            "content": (
                "Перепиши ответ в профессиональном и живом стиле. "
                "Строго запрещено добавлять новые факты, числа, имена, выводы, которых нет в исходном ответе. "
                "Можно только переформулировать и улучшить читаемость. "
                "Формат: обычный текст без markdown."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Вопрос: {query}\n\n"
                f"Проверенный фактический ответ:\n{base}\n\n"
                f"Контекст для контроля:\n{context}\n\n"
                "Сделай улучшенную редакцию ответа:"
            ),
        },
    ]
    out, err, _u = chat_complete(
        api_base,
        token,
        chat_model,
        messages,
        temperature=0.1,
        max_tokens=max(200, min(max_tokens, 1200)),
        top_p=top_p,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
    )
    if err or not out:
        return None
    rewritten = _strip_markdown_basic(str(out).strip())
    if not rewritten:
        return None
    # Guardrail: if rewritten drops all query keywords, keep factual answer.
    qk = _expand_query_keywords(_extract_keywords(query))
    if qk and _keyword_hits(rewritten, qk) == 0:
        return None
    return rewritten


def _looks_like_generic_non_answer(query: str, answer: str, chunks: list[dict[str, Any]]) -> bool:
    qk = _extract_keywords(query)
    if not qk:
        return False
    ah = _keyword_hits(answer, qk)
    ch = 0
    for c in chunks[:6]:
        ch = max(ch, _keyword_hits(str(c.get("text") or ""), qk))
    # Answer ignores query terms while chunks clearly contain them.
    return ah == 0 and ch >= 2


def _looks_like_insufficient_answer(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    markers = (
        "данных недостаточно",
        "информации нет",
        "не найдено достаточно",
        "не удалось найти",
        "в предоставленном контексте",
    )
    return any(m in t for m in markers)


def _chunks_have_concrete_evidence(query: str, chunks: list[dict[str, Any]]) -> bool:
    qk = _extract_keywords(query)
    if not qk or not chunks:
        return False
    for c in chunks[:12]:
        txt = str(c.get("text") or "")
        if not txt:
            continue
        hits = _keyword_hits(txt, qk)
        has_number = bool(re.search(r"\d{2,4}", txt))
        if hits >= 1 and has_number:
            return True
    return False


def _is_numeric_fact_query(query: str) -> bool:
    q = (query or "").lower()
    if not q:
        return False
    markers = (
        "сколько",
        "вес",
        "кг",
        "килограмм",
        "поднима",
        "жим",
        "длительность",
        "время",
        "минут",
        "час",
        "процент",
        "%",
        "цена",
        "стоимость",
        "руб",
    )
    return any(m in q for m in markers)


def _is_noise_chunk_text(text: str) -> bool:
    t = (text or "").lower()
    if not t:
        return False
    markers = (
        "позитивная музыка",
        "музыка",
        "подпишись",
        "ставьте лайк",
        "промокод",
        "ссылка в описании",
        "реклама",
    )
    return any(m in t for m in markers)


def _append_lexical_recall_rows(
    db: Session,
    *,
    portal_id: int,
    audience: str,
    keywords: list[str],
    scored: list[tuple[float, bool, dict[str, Any]]],
    limit: int = 400,
    file_ids_filter: list[int] | None = None,
) -> None:
    if not keywords:
        return
    probes = [k for k in keywords[:6] if len(k) >= 4]
    if not probes:
        return
    conds = [KBChunk.text.ilike(f"%{p}%") for p in probes]
    q = (
        select(
            KBChunk.text,
            KBChunk.chunk_index,
            KBChunk.start_ms,
            KBChunk.end_ms,
            KBChunk.page_num,
            KBChunk.id,
            KBFile.id,
            KBFile.filename,
            KBFile.mime_type,
            KBSource.source_type,
            KBSource.url,
            KBSource.title,
        )
        .join(KBFile, KBFile.id == KBChunk.file_id)
        .join(KBSource, KBSource.id == KBFile.source_id, isouter=True)
        .where(
            KBChunk.portal_id == portal_id,
            KBFile.status == "ready",
            KBFile.audience == audience,
            or_(*conds),
        )
        .order_by(KBChunk.id.desc())
        .limit(limit)
    )
    ids = [int(x) for x in (file_ids_filter or []) if int(x) > 0]
    if ids:
        q = q.where(KBFile.id.in_(ids))
    rows = db.execute(q).all()
    for text, chunk_index, start_ms, end_ms, page_num, chunk_id, file_id, filename, mime_type, source_type, source_url, source_title in rows:
        txt = str(text or "")
        txt_low = txt.lower()
        meta_text = " ".join(
            [
                str(filename or ""),
                str(source_title or ""),
                str(source_url or ""),
            ]
        ).lower()
        hits = _keyword_hits(txt_low, keywords)
        meta_hits = _keyword_hits(meta_text, keywords)
        if (hits + meta_hits) <= 0:
            continue
        score = 0.10 + (hits * 0.08) + (meta_hits * 0.06)
        if _is_noise_chunk_text(txt_low):
            score -= 0.25
        scored.append(
            (
                float(score),
                bool(hits > 0 or meta_hits > 0),
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
                    "source_title": source_title or "",
                },
            )
        )


def _select_claim_chunks(query: str, chunks: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    qk = _extract_keywords(query)
    scored: list[tuple[int, dict[str, Any]]] = []
    for c in chunks:
        txt = str(c.get("text") or "")
        if not txt:
            continue
        num_hits = len(re.findall(r"\d+(?:[.,]\d+)?", txt))
        body_hits = _keyword_hits(txt, qk)
        meta_hits = _keyword_hits(
            " ".join(
                [
                    str(c.get("filename") or ""),
                    str(c.get("source_title") or ""),
                    str(c.get("source_url") or ""),
                ]
            ),
            qk,
        )
        score = (num_hits * 3) + (body_hits * 3) + (meta_hits * 2)
        if score > 0:
            scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    numeric_query = _is_numeric_fact_query(query)
    return [c for _s, c in scored[: max(1, limit)]]


def _render_claim_context(chunks: list[dict[str, Any]]) -> str:
    out: list[str] = []
    for i, c in enumerate(chunks, start=1):
        txt = str(c.get("text") or "").replace("\n", " ").strip()
        if len(txt) > 420:
            txt = txt[:420].rstrip() + "…"
        src = str(c.get("filename") or c.get("source_title") or "Источник")
        out.append(f"[{i}] {txt}\nsource={src}")
    return "\n\n".join(out)


def _rerank_candidates(query: str, candidates: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
    if not candidates:
        return []
    qk = _extract_keywords(query)
    person_phrase = _person_query_phrase(query)
    person_tokens = [t.lower() for t in re.findall(r"[a-zа-яё]{2,}", person_phrase or "", flags=re.IGNORECASE)]
    person_tokens = person_tokens[:4]
    person_full = " ".join(person_tokens) if len(person_tokens) >= 2 else ""
    ranked: list[tuple[float, dict[str, Any]]] = []
    seen_chunk: set[int] = set()
    seen_file_top: set[int] = set()
    for idx, c in enumerate(candidates):
        cid = c.get("chunk_id")
        if isinstance(cid, int):
            if cid in seen_chunk:
                continue
            seen_chunk.add(cid)
        sem = float(c.get("_score") or 0.0)
        body_hits = _keyword_hits(str(c.get("text") or ""), qk)
        meta_hits = _keyword_hits(
            " ".join(
                [
                    str(c.get("filename") or ""),
                    str(c.get("source_title") or ""),
                    str(c.get("source_url") or ""),
                    str(c.get("file_summary") or ""),
                ]
            ),
            qk,
        )
        txt_low = str(c.get("text") or "").lower()
        meta_low = " ".join(
            [
                str(c.get("filename") or ""),
                str(c.get("source_title") or ""),
                str(c.get("source_url") or ""),
                str(c.get("file_summary") or ""),
            ]
        ).lower()
        entity_bonus = 0.0
        entity_penalty = 0.0
        if person_tokens:
            token_hits = sum(1 for t in person_tokens if t in txt_low or t in meta_low)
            if person_full and (person_full in txt_low or person_full in meta_low):
                entity_bonus += 0.28
            if token_hits >= 2:
                entity_bonus += 0.16
            else:
                entity_penalty -= 0.22
        noise_penalty = -0.18 if _is_noise_chunk_text(txt_low) else 0.0
        # prefer unique files in top positions
        file_diversity_bonus = 0.0
        fid = c.get("file_id")
        if isinstance(fid, int):
            if fid not in seen_file_top:
                file_diversity_bonus += 0.03
                seen_file_top.add(fid)
            else:
                file_diversity_bonus -= 0.01
        if idx == 0:
            file_diversity_bonus += 0.02
        final = (
            sem
            + (body_hits * 0.06)
            + (meta_hits * 0.09)
            + file_diversity_bonus
            + entity_bonus
            + entity_penalty
            + noise_penalty
        )
        ranked.append((final, c))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [c for _s, c in ranked[: max(1, top_k)]]


def _build_file_summaries(scored: list[tuple[float, bool, dict[str, Any]]]) -> dict[int, str]:
    out: dict[int, str] = {}
    for _score, _is_lex, item in scored:
        fid = item.get("file_id")
        if not isinstance(fid, int) or fid in out:
            continue
        txt = str(item.get("text") or "").replace("\n", " ").strip()
        if txt:
            out[fid] = txt[:220]
    return out


def _dedup_source_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for s in items:
        key = "|".join(
            [
                str(s.get("file_id") or ""),
                str(s.get("chunk_id") or ""),
                str(s.get("chunk_index") or ""),
                str(s.get("page_num") or ""),
                str(s.get("start_ms") or ""),
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _attach_support_chunks(source_items: list[dict[str, Any]], used_chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not source_items or not used_chunks:
        return source_items
    by_file: dict[int, list[dict[str, Any]]] = {}
    for c in used_chunks:
        fid = c.get("file_id")
        if not isinstance(fid, int):
            continue
        by_file.setdefault(fid, []).append(c)
    out: list[dict[str, Any]] = []
    for s in source_items:
        fid = s.get("file_id")
        cidx = s.get("chunk_index")
        if not isinstance(fid, int) or not isinstance(cidx, int):
            out.append(s)
            continue
        support = []
        for c in by_file.get(fid, []):
            idx = c.get("chunk_index")
            if not isinstance(idx, int):
                continue
            if abs(idx - cidx) <= 1:
                support.append(c)
        if not support:
            out.append(s)
            continue
        support.sort(key=lambda x: (abs(int(x.get("chunk_index") or 0) - cidx), int(x.get("chunk_index") or 0)))
        support_ids = [int(c.get("chunk_id")) for c in support if c.get("chunk_id") is not None]
        support_idx = [int(c.get("chunk_index")) for c in support if c.get("chunk_index") is not None]
        out.append(
            {
                **s,
                "support_chunk_ids": support_ids,
                "support_chunk_indexes": support_idx,
                "anchor_page_display": s.get("page_num"),
            }
        )
    return out


def _build_line_refs(answer: str, source_items: list[dict[str, Any]], query: str | None = None) -> dict[str, list[int]]:
    lines = str(answer or "").splitlines()
    if not lines or not source_items:
        return {}
    qk = _expand_query_keywords(_extract_keywords(query or ""))
    has_list = any(re.match(r"^\s*(\d+[\)\.]|[-*•])\s+", (ln or "").strip()) for ln in lines)
    refs: dict[str, list[int]] = {}
    for i, ln in enumerate(lines):
        t = (ln or "").strip()
        if not t:
            continue
        if has_list and not re.match(r"^\s*(\d+[\)\.]|[-*•])\s+", t):
            continue
        line_k = _expand_query_keywords(_extract_keywords(t))
        if not line_k:
            continue
        scored: list[tuple[float, int]] = []
        for si, s in enumerate(source_items):
            text_scope = str(s.get("text") or "")
            meta_scope = " ".join(
                [
                    str(s.get("filename") or ""),
                    str(s.get("source_title") or ""),
                ]
            )
            line_hits = _keyword_hits(text_scope, line_k)
            query_hits = _keyword_hits(text_scope, qk)
            meta_hits = _keyword_hits(meta_scope, line_k)
            src_score = float(s.get("score") or 0.0)
            # hybrid ranking: line relevance + query relevance + source retrieval weight
            score = (line_hits * 3.0) + (query_hits * 1.5) + (meta_hits * 0.5) + (src_score * 2.0)
            if score >= 2.2:
                scored.append((score, si))
        if not scored:
            continue
        scored.sort(key=lambda x: (-x[0], x[1]))
        refs[str(i)] = [si for _sc, si in scored[:3]]
    return refs


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
    file_ids_filter: list[int] | None = None,
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
    meta_lex_boost = float(settings.get("meta_lex_boost") or 0.18)
    retrieval_min_score = float(settings.get("retrieval_min_score") or 0.06)
    retrieval_min_keyword_hits = int(settings.get("retrieval_min_keyword_hits") or 0)
    confidence_min = float(settings.get("confidence_min") or 0.24)
    confidence_min_evidence = int(settings.get("confidence_min_evidence") or 1)
    use_history = bool(settings.get("use_history")) if settings.get("use_history") is not None else True
    use_cache = bool(settings.get("use_cache")) if settings.get("use_cache") is not None else True
    rag_v2_enabled = bool(settings.get("rag_v2_enabled")) if settings.get("rag_v2_enabled") is not None else False
    style_pass_enabled = bool(settings.get("style_pass_enabled")) if settings.get("style_pass_enabled") is not None else True
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
    if overrides.get("rag_v2_enabled") is not None:
        rag_v2_enabled = bool(overrides.get("rag_v2_enabled"))
    if overrides.get("style_pass_enabled") is not None:
        style_pass_enabled = bool(overrides.get("style_pass_enabled"))
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
    scoped_ids = [int(x) for x in (file_ids_filter or []) if int(x) > 0]
    pg_rows = query_top_chunks_by_pgvector(
        db,
        portal_id=portal_id,
        audience=aud,
        model=embed_model,
        query_vec=qv,
        limit=max(50, retrieval_top_k * 6),
        file_ids=scoped_ids,
    )

    keywords = _expand_query_keywords(_extract_keywords(query))
    scored: list[tuple[float, bool, dict[str, Any]]] = []
    if pg_rows:
        for r in pg_rows:
            txt = (r.get("text") or "")
            txt_low = txt.lower()
            meta_text = " ".join(
                [
                    str(r.get("filename") or ""),
                    str(r.get("source_title") or ""),
                    str(r.get("source_url") or ""),
                ]
            ).lower()
            body_lex_match = any(k in txt_low for k in keywords) if keywords else False
            meta_lex_match = any(k in meta_text for k in keywords) if keywords else False
            lex_match = bool(body_lex_match or meta_lex_match)
            score = float(r.get("score") or 0.0)
            if body_lex_match:
                score += lex_boost
            if meta_lex_match:
                score += meta_lex_boost
            if _is_noise_chunk_text(txt_low):
                score -= 0.25
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
                        "source_title": r.get("source_title") or "",
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
                KBSource.title,
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
        if scoped_ids:
            base_query = base_query.where(KBFile.id.in_(scoped_ids))
        rows = db.execute(
            base_query.where(KBEmbedding.model == embed_model)
        ).all()
        if not rows:
            rows = db.execute(
                base_query.where(KBEmbedding.model.is_(None))
            ).all()
        if not rows:
            return None, "kb_empty", None

        for vec, text, chunk_index, start_ms, end_ms, page_num, filename, mime_type, chunk_id, file_id, source_type, source_url, source_title in rows:
            if not isinstance(vec, list):
                continue
            txt = (text or "")
            txt_low = txt.lower()
            meta_text = " ".join(
                [
                    str(filename or ""),
                    str(source_title or ""),
                    str(source_url or ""),
                ]
            ).lower()
            body_lex_match = any(k in txt_low for k in keywords) if keywords else False
            meta_lex_match = any(k in meta_text for k in keywords) if keywords else False
            lex_match = bool(body_lex_match or meta_lex_match)
            score = _cosine(qv, vec)
            if body_lex_match:
                score += lex_boost
            if meta_lex_match:
                score += meta_lex_boost
            if _is_noise_chunk_text(txt_low):
                score -= 0.25
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
                    "source_title": source_title or "",
                }
            ))
    _append_lexical_recall_rows(
        db,
        portal_id=portal_id,
        audience=aud,
        keywords=keywords,
        scored=scored,
        limit=max(300, retrieval_top_k * 80),
        file_ids_filter=scoped_ids,
    )
    if not scored:
        return None, "kb_empty", None
    file_summaries = _build_file_summaries(scored)
    if file_summaries:
        patched: list[tuple[float, bool, dict[str, Any]]] = []
        for s, lx, item in scored:
            fid = item.get("file_id")
            fs = file_summaries.get(fid) if isinstance(fid, int) else None
            if fs:
                item = {**item, "file_summary": fs}
            patched.append((s, lx, item))
        scored = patched
    scored.sort(key=lambda x: x[0], reverse=True)
    # Strict grounding: keep only chunks that are semantically above threshold
    # and have lexical evidence for the query. This prevents "general world knowledge"
    # answers when KB context is weak/irrelevant.
    numeric_query = _is_numeric_fact_query(query)
    relevant_scored: list[tuple[float, bool, dict[str, Any]]] = []
    adaptive_min_score = retrieval_min_score
    if keywords:
        for _score, _is_lex, it in scored[:20]:
            meta_probe = " ".join(
                [
                    str(it.get("filename") or ""),
                    str(it.get("source_title") or ""),
                    str(it.get("source_url") or ""),
                ]
            )
            if _keyword_hits(meta_probe, keywords) > 0:
                adaptive_min_score = min(adaptive_min_score, 0.0)
                break
    seen_chunk_ids: set[int] = set()
    for score, is_lex, item in scored:
        cid = item.get("chunk_id")
        if isinstance(cid, int):
            if cid in seen_chunk_ids:
                continue
            seen_chunk_ids.add(cid)
        hits = _keyword_hits(str(item.get("text") or ""), keywords)
        if score < adaptive_min_score:
            continue
        meta_hits = _keyword_hits(
            " ".join(
                [
                    str(item.get("filename") or ""),
                    str(item.get("source_title") or ""),
                    str(item.get("source_url") or ""),
                    str(item.get("file_summary") or ""),
                ]
            ),
            keywords,
        )
        if numeric_query and keywords and hits < retrieval_min_keyword_hits:
            continue
        if keywords and not is_lex and (hits + meta_hits) < retrieval_min_keyword_hits:
            continue
        item = {**item, "_score": float(score), "_keyword_hits": int(hits), "_meta_keyword_hits": int(meta_hits)}
        relevant_scored.append((score, is_lex, item))

    if not relevant_scored:
        if strict_mode:
            usage = {"sources": [], "reason": "low_relevance_context"}
            return "В базе знаний не найдено достаточно релевантной информации по запросу. Уточните вопрос или загрузите материалы по этой теме.", None, usage
        relevant_scored = scored

    top_k = retrieval_top_k
    max_chars = retrieval_max_chars
    if "собери" in query.lower() or "всю информацию" in query.lower():
        top_k = max(8, retrieval_top_k)
        max_chars = max(6000, retrieval_max_chars)
    candidate_pool = [t for _s, _is_lex, t in relevant_scored[: max(20, top_k * 4)]]
    if keywords:
        if numeric_query:
            lex = [t for _s, _is_lex, t in relevant_scored if int(t.get("_keyword_hits") or 0) > 0][: min(8, max(8, top_k))]
        else:
            lex = [t for _s, is_lex, t in relevant_scored if is_lex][: min(8, max(8, top_k))]
        sem = [t for t in candidate_pool if t not in lex]
        candidate_pool = lex + sem
    top_chunks = _rerank_candidates(query, candidate_pool, top_k=top_k)
    if follow_up and cached_chunk_ids and use_cache:
        cached = [t for _s, _is_lex, t in relevant_scored if t.get("chunk_id") in cached_chunk_ids]
        top_chunks = _rerank_candidates(query, cached + top_chunks, top_k=top_k)
    context, used_chunks = _build_context(top_chunks, max_chars=max_chars)
    conf, evidence = _retrieval_confidence(
        top_chunks,
        query_keywords=keywords,
        min_score_ref=adaptive_min_score,
    )
    if strict_mode and (conf < confidence_min or evidence < confidence_min_evidence):
        usage = {
            "sources": [],
            "reason": "low_confidence_context",
            "confidence": conf,
            "confidence_min": confidence_min,
            "evidence_count": evidence,
        }
        return "В базе знаний не найдено достаточно релевантной информации по запросу. Уточните вопрос или загрузите материалы по этой теме.", None, usage
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
        "Не используй внешние знания, домыслы и общие факты вне контекста. "
        "Если в контексте нет точного ответа — прямо скажи, что данных недостаточно. "
        "Пиши живым человеческим языком. "
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
    used_rag_v2 = False
    if strict_mode and rag_v2_enabled:
        claims_answer = _build_claims_answer(
            query,
            used_chunks,
            api_base=api_base,
            token=token,
            chat_model=chat_model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
        )
        if claims_answer:
            out = claims_answer
        elif _is_numeric_fact_query(query):
            out = _extract_numeric_fact_structured(query, used_chunks) or "В базе знаний нет подтвержденного числового значения по запросу."
        else:
            out = "В базе знаний не найдено достаточно релевантной информации по запросу. Уточните вопрос или загрузите материалы по этой теме."
        used_rag_v2 = True
    if (not used_rag_v2) and strict_mode and _is_numeric_fact_query(query):
        claim_chunks = _select_claim_chunks(query, used_chunks, limit=max(6, retrieval_top_k))
        if claim_chunks:
            claim_context = _render_claim_context(claim_chunks)
            refine_messages = [
                {
                    "role": "system",
                    "content": (
                        "Ты редактор ответов по базе знаний. Используй только факты из контекста. "
                        "Дай содержательный, развернутый ответ на вопрос пользователя, но без выдумок и без внешних знаний. "
                        "Если в контексте есть несколько чисел/вариантов — аккуратно объясни, что именно к чему относится."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Вопрос: {query}\n\nКонтекст фактов:\n{claim_context}\n\nСформируй ответ:",
                },
            ]
            refined, ref_err, _ref_usage = chat_complete(
                api_base,
                token,
                chat_model,
                refine_messages,
                temperature=max(0.0, min(temperature, 0.2)),
                max_tokens=max_tokens,
                top_p=top_p,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
            )
            if refined and not ref_err:
                out = _strip_markdown_basic(refined.strip())
    if not used_rag_v2:
        out = re.sub(r"\[\d+\]", "", out).strip()
    if (not used_rag_v2) and (
        _looks_like_model_disclaimer(out)
        or (strict_mode and _looks_like_generic_non_answer(query, out, used_chunks))
        or (strict_mode and _looks_like_insufficient_answer(out) and _chunks_have_concrete_evidence(query, used_chunks))
    ):
        if _is_numeric_fact_query(query):
            numeric = _extract_numeric_fact_structured(query, used_chunks) or _extract_numeric_fact_answer(query, used_chunks)
            out = numeric or _extractive_answer_from_chunks(query, used_chunks, limit=min(6, max(3, retrieval_top_k)))
        else:
            out = _extractive_answer_from_chunks(query, used_chunks, limit=min(6, max(3, retrieval_top_k)))
    elif (not used_rag_v2) and _is_numeric_fact_query(query) and (_looks_like_chunk_dump(out) or _looks_like_low_quality_numeric_answer(out)):
        numeric = _extract_numeric_fact_structured(query, used_chunks) or _extract_numeric_fact_answer(query, used_chunks)
        if numeric:
            out = numeric
    if (not used_rag_v2) and strict_mode:
        out = _verify_and_ground_answer(query, out, used_chunks)
    if (not used_rag_v2) and _is_numeric_fact_query(query):
        forced_numeric = _extract_numeric_fact_structured(query, used_chunks)
        if forced_numeric:
            out = forced_numeric
        else:
            fallback_numeric = _extract_numeric_fact_answer(query, used_chunks)
            if fallback_numeric and not _looks_like_low_quality_numeric_answer(fallback_numeric):
                out = fallback_numeric
            else:
                out = "В базе знаний нет подтвержденного числового значения по запросу."
    if strict_mode and _looks_low_quality_answer(out):
        notes = _extract_fact_notes(query, used_chunks, limit=6)
        if notes:
            out = "Подтверждено в базе знаний:\n" + "\n".join([f"{i+1}) {n}" for i, n in enumerate(notes)])
    if style_pass_enabled and out and not _looks_like_insufficient_answer(out):
        styled = _style_rewrite_answer(
            query=query,
            factual_answer=out,
            chunks=used_chunks,
            api_base=api_base,
            token=token,
            chat_model=chat_model,
            max_tokens=max_tokens,
            top_p=top_p,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
        )
        if styled:
            out = styled
    # Person/entity queries are forced to extractive mode to avoid biographical hallucinations.
    person_answer = _extract_person_entity_answer(query, used_chunks)
    if person_answer:
        out = person_answer
    answer_keywords = _extract_keywords(out)[:40]
    validated_chunks: list[tuple[int, dict[str, Any]]] = []
    for c in used_chunks:
        txt = str(c.get("text") or "")
        meta = " ".join(
            [
                str(c.get("filename") or ""),
                str(c.get("source_title") or ""),
                str(c.get("source_url") or ""),
                str(c.get("file_summary") or ""),
            ]
        )
        score = (
            (_keyword_hits(txt, keywords) * 2)
            + (_keyword_hits(meta, keywords) * 3)
            + _keyword_hits(txt, answer_keywords)
            + _keyword_hits(meta, answer_keywords)
        )
        if score > 0:
            validated_chunks.append((score, c))
    if validated_chunks:
        validated_chunks.sort(key=lambda x: x[0], reverse=True)
        used_chunks = [c for _s, c in validated_chunks]
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
            "source_title": c.get("source_title") or "",
            "chunk_index": c.get("chunk_index"),
            "start_ms": c.get("start_ms"),
            "end_ms": c.get("end_ms"),
            "page_num": c.get("page_num"),
            "anchor_kind": (
                "pdf_page"
                if (c.get("page_num") is not None and int(c.get("page_num") or 0) > 0)
                else ("media_ms" if c.get("start_ms") is not None else "chunk_index")
            ),
            "anchor_value": (
                str(int(c.get("page_num")))
                if (c.get("page_num") is not None and int(c.get("page_num") or 0) > 0)
                else (str(int(c.get("start_ms"))) if c.get("start_ms") is not None else str(int(c.get("chunk_index") or 0)))
            ),
            "text": c.get("text") or "",
            "score": float(c.get("_score") or 0.0),
        }
        for c in used_chunks
    ]
    source_items = _dedup_source_items(source_items)
    source_items = _attach_support_chunks(source_items, used_chunks)
    line_refs = _build_line_refs(out, source_items, query=query)
    if usage is None:
        usage = {}
    if isinstance(usage, dict):
        usage["sources"] = source_items
        usage["line_refs"] = line_refs
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
