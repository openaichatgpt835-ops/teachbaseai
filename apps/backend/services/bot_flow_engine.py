"""Bot flow execution for client bot."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.backend.models.portal_bot_flow import PortalBotFlow
from apps.backend.models.dialog_state import DialogState
from apps.backend.models.portal import Portal
from apps.backend.services.kb_rag import answer_from_kb
from apps.backend.services.bitrix_auth import rest_call_with_refresh

logger = logging.getLogger(__name__)


def _default_flow() -> dict[str, Any]:
    return {
        "version": 1,
        "settings": {
            "mood": "нейтральный",
            "custom_prompt": "",
            "use_history": True,
        },
        "nodes": [
            {"id": "start", "type": "start", "title": "Start"},
            {"id": "kb", "type": "kb_answer", "title": "KB Ответ"},
        ],
        "edges": [
            {"from": "start", "to": "kb"},
        ],
    }


def _get_flow(db: Session, portal_id: int, kind: str = "client") -> dict[str, Any]:
    row = db.get(PortalBotFlow, {"portal_id": portal_id, "kind": kind})
    if not row or not row.published_json:
        return _default_flow()
    return row.published_json or _default_flow()


def _get_state(db: Session, dialog_id: int) -> dict[str, Any]:
    row = db.get(DialogState, dialog_id)
    if not row or not row.state_json:
        return {"vars": {}, "pending": None}
    return row.state_json or {"vars": {}, "pending": None}


def _save_state(db: Session, dialog_id: int, state: dict[str, Any]) -> None:
    row = db.get(DialogState, dialog_id)
    if not row:
        row = DialogState(dialog_id=dialog_id, state_json=state)
        db.add(row)
    else:
        row.state_json = state
    db.commit()


def _find_node(nodes: list[dict[str, Any]], node_id: str) -> dict[str, Any] | None:
    for n in nodes:
        if n.get("id") == node_id:
            return n
    return None


def _out_edges(edges: list[dict[str, Any]], node_id: str) -> list[dict[str, Any]]:
    return [e for e in edges if e.get("from") == node_id]


def _render_template(text: str, vars_map: dict[str, Any]) -> str:
    if not text:
        return text
    out = text
    for k, v in vars_map.items():
        out = out.replace("{{" + k + "}}", str(v))
    return out


def _parse_phrases(raw: Any) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    text = str(raw)
    parts = re.split(r"[\n,;]+", text)
    return [p.strip() for p in parts if p.strip()]


def _meaning_score(text: str, phrases: list[str]) -> float:
    if not text or not phrases:
        return 0.0
    t = text.lower()
    hits = 0
    for p in phrases:
        if p.lower() in t:
            hits += 1
    return hits / max(1, len(phrases))


def _select_meaning(text: str, meanings: list[dict[str, Any]]) -> tuple[str | None, float, str | None]:
    if not meanings:
        return None, 0.0, None
    best_id = None
    best_score = 0.0
    best_title = None
    for idx, m in enumerate(meanings):
        phrases = _parse_phrases(m.get("phrases") or m.get("core") or [])
        score = _meaning_score(text, phrases)
        try:
            threshold = float(m.get("sensitivity") or 0.5)
        except Exception:
            threshold = 0.5
        if score >= threshold and score >= best_score:
            best_score = score
            best_id = str(m.get("id") or m.get("key") or m.get("title") or f"meaning_{idx}")
            best_title = str(m.get("title") or best_id)
    return best_id, best_score, best_title


def _match_condition(cond: dict[str, Any], text: str, vars_map: dict[str, Any]) -> bool:
    if not cond:
        return True
    # support rule groups
    if cond.get("rules") and isinstance(cond.get("rules"), list):
        mode = (cond.get("mode") or "any").lower()
        results = [bool(_match_condition(c, text, vars_map)) for c in cond.get("rules") if c]
        if not results:
            return False
        return all(results) if mode == "all" else any(results)
    op = (cond.get("op") or "contains").lower()
    src = cond.get("src") or "input"
    value = cond.get("value") or ""
    if op == "meaning":
        return str(vars_map.get("_meaning") or "").strip().lower() == str(value).strip().lower()
    if src == "meaning":
        text_val = str(vars_map.get("_meaning") or "")
    elif src.startswith("var:"):
        key = src.split(":", 1)[1]
        text_val = str(vars_map.get(key) or "")
    else:
        text_val = text or ""
    if op == "equals":
        return text_val.strip().lower() == str(value).strip().lower()
    if op == "regex":
        try:
            return re.search(str(value), text_val, flags=re.IGNORECASE) is not None
        except re.error:
            return False
    return str(value).strip().lower() in text_val.strip().lower()


def _has_meaningful_condition(cond: dict[str, Any] | None) -> bool:
    if not cond:
        return False
    rules = cond.get("rules")
    mode = (cond.get("mode") or "").lower()
    if isinstance(rules, list):
        return mode in ("any", "all") and any(
            (r or {}).get("value") not in (None, "") for r in rules
        )
    return bool(cond.get("op") or cond.get("value") or cond.get("src"))


def _select_next(edges: list[dict[str, Any]], text: str, vars_map: dict[str, Any]) -> str | None:
    # first match with condition
    for e in edges:
        cond = e.get("condition")
        if _has_meaningful_condition(cond) and _match_condition(cond, text, vars_map):
            return e.get("to")
    # default edge (no condition)
    for e in edges:
        if not _has_meaningful_condition(e.get("condition")):
            return e.get("to")
    return None


def _execute_flow(
    db: Session,
    portal_id: int,
    dialog_id: int,
    user_text: str,
    *,
    flow: dict[str, Any],
    preview: bool = False,
    state_override: dict[str, Any] | None = None,
    collect_trace: bool = False,
) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    nodes = flow.get("nodes") or []
    edges = flow.get("edges") or []
    settings = flow.get("settings") or {}
    vars_map = {}
    state = state_override if state_override is not None else ({"vars": {}, "pending": None} if preview else _get_state(db, dialog_id))
    vars_map.update(state.get("vars") or {})
    pending = state.get("pending")
    trace: list[dict[str, Any]] = []

    def _trace(event: str, node: dict[str, Any] | None = None, extra: dict[str, Any] | None = None) -> None:
        if not collect_trace:
            return
        payload: dict[str, Any] = {"event": event}
        if node:
            payload.update({"id": node.get("id"), "type": node.get("type"), "title": node.get("title")})
        if extra:
            payload.update(extra)
        trace.append(payload)

    responses: list[str] = []
    current_id = "start"
    if pending:
        # resolve pending ask
        var_name = pending.get("var") or "input"
        vars_map[var_name] = user_text
        current_id = pending.get("next") or "start"
        state["pending"] = None
        _trace("pending_resolved", extra={"var": var_name})

    steps = 0
    visited: dict[str, int] = {}
    while steps < 20 and current_id:
        steps += 1
        node = _find_node(nodes, current_id)
        if not node:
            break
        ntype = (node.get("type") or "").lower()
        config = node.get("config") or {}
        _trace("node", node)
        visited[current_id] = visited.get(current_id, 0) + 1
        if visited[current_id] > 1 and ntype in ("message", "kb_answer", "ask", "branch", "prompt", "webhook", "bitrix_lead", "bitrix_deal"):
            _trace("loop_break", node)
            break

        if ntype == "start":
            nxt = _select_next(_out_edges(edges, current_id), user_text, vars_map)
            _trace("edge", node, {"to": nxt})
            current_id = nxt
            continue

        if ntype == "message":
            text = _render_template(config.get("text") or "", vars_map)
            if text:
                responses.append(text)
            current_id = _select_next(_out_edges(edges, current_id), user_text, vars_map)
            _trace("edge", node, {"to": current_id})
            continue

        if ntype == "ask":
            question = _render_template(config.get("question") or "", vars_map)
            var_name = (config.get("var") or "answer").strip()
            nxt = _select_next(_out_edges(edges, current_id), user_text, vars_map)
            state["pending"] = {"var": var_name, "next": nxt}
            _trace("ask", node, {"var": var_name, "next": nxt})
            if question:
                responses.append(question)
            break

        if ntype == "branch":
            meanings = config.get("meanings") or []
            meaning_id, meaning_score, meaning_title = _select_meaning(user_text, meanings)
            if meaning_id:
                vars_map["_meaning"] = meaning_id
                vars_map["_meaning_score"] = meaning_score
                vars_map["_meaning_title"] = meaning_title
                _trace("meaning", node, {"meaning": meaning_id, "score": meaning_score, "title": meaning_title})
            else:
                vars_map.pop("_meaning", None)
                vars_map.pop("_meaning_score", None)
                vars_map.pop("_meaning_title", None)
            nxt = _select_next(_out_edges(edges, current_id), user_text, vars_map)
            _trace("edge", node, {"to": nxt})
            current_id = nxt
            continue

        if ntype == "prompt":
            # update runtime prompt
            mood = (config.get("mood") or settings.get("mood") or "neutral").strip().lower()
            custom = (config.get("custom_prompt") or settings.get("custom_prompt") or "").strip()
            vars_map["_mood"] = mood
            vars_map["_custom_prompt"] = custom
            if config.get("pre_prompt"):
                vars_map["_pre_prompt"] = str(config.get("pre_prompt") or "").strip()
            current_id = _select_next(_out_edges(edges, current_id), user_text, vars_map)
            _trace("edge", node, {"to": current_id})
            continue

        if ntype == "kb_answer":
            mood = (vars_map.get("_mood") or settings.get("mood") or "нейтральный").strip().lower()
            custom = (vars_map.get("_custom_prompt") or settings.get("custom_prompt") or "").strip()
            pre_prompt = (config.get("pre_prompt") or vars_map.get("_pre_prompt") or "").strip()
            mood_map = {
                "нейтральный": "Отвечай нейтрально и профессионально.",
                "дружелюбный": "Отвечай дружелюбно и поддерживающе.",
                "продающий": "Отвечай с легким sales-акцентом и фокусом на ценности.",
                "строгий": "Отвечай строго по фактам, без лишних эмоций.",
            }
            extra = mood_map.get(mood, "")
            if custom:
                extra = (extra + " " + custom).strip()
            if pre_prompt:
                extra = (extra + " " + pre_prompt).strip() if extra else pre_prompt
            # override system_prompt_extra via temp setting injection
            answer, err, _usage = answer_from_kb(
                db,
                portal_id,
                user_text,
                dialog_id=dialog_id if settings.get("use_history", True) else None,
                audience="client",
                system_prompt_extra_override=extra if extra else None,
                model_overrides=config.get("model_override") or None,
            )
            if answer:
                if extra:
                    # prepend mood hint if no other nodes handle it
                    responses.append(answer)
                else:
                    responses.append(answer)
            else:
                responses.append("Извините, я пока не могу ответить на этот вопрос.")
            current_id = _select_next(_out_edges(edges, current_id), user_text, vars_map)
            _trace("edge", node, {"to": current_id})
            continue

        if ntype == "webhook":
            url = (config.get("url") or "").strip()
            payload = config.get("payload") or {}
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    payload = {}
            payload_rendered = json.loads(json.dumps(payload)) if payload else {}
            payload_rendered["text"] = user_text
            payload_rendered["portal_id"] = portal_id
            payload_rendered["vars"] = vars_map
            if url:
                try:
                    httpx.post(url, json=payload_rendered, timeout=10)
                except Exception as e:
                    logger.warning("webhook failed: %s", e)
            current_id = _select_next(_out_edges(edges, current_id), user_text, vars_map)
            _trace("edge", node, {"to": current_id})
            continue

        if ntype in ("bitrix_lead", "bitrix_deal"):
            portal = db.get(Portal, portal_id)
            if portal and portal.domain:
                method = "crm.lead.add" if ntype == "bitrix_lead" else "crm.deal.add"
                fields = config.get("fields") or {}
                if isinstance(fields, str):
                    try:
                        fields = json.loads(fields)
                    except Exception:
                        fields = {}
                rendered = {}
                for k, v in fields.items():
                    rendered[k] = _render_template(str(v), vars_map)
                try:
                    rest_call_with_refresh(
                        db, portal_id, method, {"fields": rendered}, trace_id="flow"
                    )
                except Exception as e:
                    logger.warning("bitrix crm add failed: %s", e)
            current_id = _select_next(_out_edges(edges, current_id), user_text, vars_map)
            _trace("edge", node, {"to": current_id})
            continue

        if ntype == "handoff":
            text = _render_template(config.get("text") or "Передаю менеджеру.", vars_map)
            responses.append(text)
            current_id = None
            continue

        # unknown node
        current_id = _select_next(_out_edges(edges, current_id), user_text, vars_map)

    state["vars"] = vars_map
    if not preview and state_override is None:
        _save_state(db, dialog_id, state)
    return "\n\n".join([r for r in responses if r]) or "Готов помочь. Задайте вопрос.", state, trace


def execute_client_flow(
    db: Session,
    portal_id: int,
    dialog_id: int,
    user_text: str,
) -> str:
    flow = _get_flow(db, portal_id, "client")
    text, _state, _trace = _execute_flow(db, portal_id, dialog_id, user_text, flow=flow, preview=False)
    return text


def execute_client_flow_preview(
    db: Session,
    portal_id: int,
    dialog_id: int,
    user_text: str,
    flow: dict[str, Any],
    state_override: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    return _execute_flow(
        db,
        portal_id,
        dialog_id,
        user_text,
        flow=flow,
        preview=True,
        state_override=state_override,
        collect_trace=True,
    )



