"""Blackbox logging for POST /v1/bitrix/events: parse, redact, hints, save, retention. Uses DB settings."""
import hashlib
import json
import logging
from urllib.parse import parse_qs
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import select, delete, func, text

from apps.backend.models.bitrix_inbound_event import BitrixInboundEvent
from apps.backend.models.portal import Portal
from apps.backend.services.inbound_settings import get_inbound_settings, DEFAULTS

logger = logging.getLogger(__name__)

BODY_MAX_BYTES_DEFAULT = 131072  # 128KB fallback

SAFE_HEADER_KEYS = frozenset(
    {"user-agent", "accept", "content-type", "x-forwarded-for", "x-request-id"}
)
REDACT_KEYS_EXACT = frozenset(
    {
        "access_token", "refresh_token", "AUTH_ID", "REFRESH_ID",
        "client_secret", "password", "token", "authorization",
    }
)


def _redact_value(val: Any, key_lower: str) -> Any:
    if isinstance(val, str) and len(val) > 80:
        if "token" in key_lower or "secret" in key_lower:
            return "***"
    return val


def _redact_obj(obj: Any, key_so_far: str = "") -> Any:
    if obj is None:
        return None
    if isinstance(obj, (int, float, bool)):
        return obj
    if isinstance(obj, str):
        return obj
    if isinstance(obj, list):
        return [_redact_obj(v, key_so_far) for v in obj]
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            key_lower = (key_so_far + "." + k).lower() if key_so_far else k.lower()
            if k in REDACT_KEYS_EXACT or key_lower in REDACT_KEYS_EXACT:
                out[k] = "***"
            elif isinstance(v, str) and len(v) > 80 and ("token" in key_lower or "secret" in key_lower):
                out[k] = "***"
            else:
                out[k] = _redact_obj(v, key_lower)
        return out
    return obj


def _safe_headers(request_headers: dict) -> dict:
    return {
        k: v for k, v in request_headers.items()
        if k.lower() in SAFE_HEADER_KEYS
    }


def _body_preview(raw: bytes, max_bytes: int = BODY_MAX_BYTES_DEFAULT) -> tuple[str, bool]:
    truncated = len(raw) > max_bytes
    chunk = raw[:max_bytes]
    try:
        return chunk.decode("utf-8"), truncated
    except UnicodeDecodeError:
        try:
            import base64
            return base64.b64encode(chunk[:512]).decode("ascii") + " (base64)", truncated
        except Exception:
            return chunk[:256].hex() + " (hex)", truncated


def _try_parse_json_value(val: str) -> Any:
    v = (val or "").strip()
    if not v:
        return val
    if v.startswith("{") or v.startswith("["):
        try:
            return json.loads(v)
        except Exception:
            return val
    return val


def _assign_bracketed(out: dict[str, Any], key: str, value: Any) -> None:
    if "[" not in key or "]" not in key:
        out[key] = value
        return
    parts: list[str] = []
    buf = ""
    i = 0
    while i < len(key):
        ch = key[i]
        if ch == "[":
            if buf:
                parts.append(buf)
                buf = ""
            j = key.find("]", i + 1)
            if j == -1:
                break
            parts.append(key[i + 1:j])
            i = j + 1
            continue
        buf += ch
        i += 1
    if buf:
        parts.append(buf)
    if not parts:
        return
    cur = out
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def _parse_body_by_content_type(content_type: str | None, body_bytes: bytes) -> dict | None:
    ct = (content_type or "").lower()
    if not body_bytes:
        return None
    if "application/json" in ct:
        try:
            parsed = json.loads(body_bytes.decode("utf-8", errors="replace"))
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            try:
                import ast
                parsed = ast.literal_eval(body_bytes.decode("utf-8", errors="replace"))
                return parsed if isinstance(parsed, dict) else None
            except Exception:
                return None
    if "application/x-www-form-urlencoded" in ct or "multipart/form-data" in ct or not ct:
        try:
            text = body_bytes.decode("utf-8", errors="replace")
        except Exception:
            text = ""
        if not text:
            return None
        if not ct and "=" not in text:
            return None
        parsed_qs = parse_qs(text, keep_blank_values=True)
        if not parsed_qs:
            return None
        out: dict[str, Any] = {}
        for k, vals in parsed_qs.items():
            if not vals:
                _assign_bracketed(out, k, "")
                continue
            val = vals[-1]
            if isinstance(val, str):
                val = _try_parse_json_value(val)
            _assign_bracketed(out, k, val)
        return out
    return None


def _extract_hints(parsed: dict | None) -> dict:
    if not parsed or not isinstance(parsed, dict):
        return {}
    hints: dict[str, Any] = {}
    event = parsed.get("event") or parsed.get("EVENT") or parsed.get("event_type")
    if event:
        hints["event_name"] = event if isinstance(event, str) else str(event)[:64]
    data = parsed.get("data") or {}
    if isinstance(data, dict):
        params = data.get("PARAMS") or data.get("params") or {}
        if not isinstance(params, dict):
            params = {}
        user_id = data.get("user_id") or data.get("USER_ID") or data.get("from_user_id") or data.get("FROM_USER_ID") or params.get("USER_ID") or params.get("user_id") or params.get("FROM_USER_ID")
        if user_id is not None:
            hints["user_id"] = user_id
        dialog_id = data.get("dialog_id") or data.get("DIALOG_ID") or data.get("chat_id") or data.get("CHAT_ID") or params.get("DIALOG_ID") or params.get("dialog_id") or params.get("CHAT_ID")
        if dialog_id is not None:
            hints["dialog_id"] = str(dialog_id)[:128]
        bots = data.get("BOT") or data.get("bot") or []
        bot_id = data.get("bot_id") or data.get("BOT_ID") or data.get("client_id") or data.get("CLIENT_ID")
        if bot_id is None and isinstance(bots, list) and bots and isinstance(bots[0], dict):
            bot_id = bots[0].get("BOT_ID") or bots[0].get("bot_id")
        if bot_id is not None:
            hints["bot_id"] = bot_id
        msg = data.get("message") or data.get("MESSAGE") or data.get("text") or params.get("MESSAGE") or params.get("message")
        if msg is not None and isinstance(msg, str):
            hints["text_len"] = len(msg)
            hints["text_hash"] = hashlib.sha256(msg.encode("utf-8", errors="replace")).hexdigest()[:16]
    auth = parsed.get("auth")
    if isinstance(auth, dict):
        domain = auth.get("domain") or auth.get("DOMAIN")
        if domain:
            hints["auth_domain"] = str(domain)[:128]
        member_id = auth.get("member_id") or auth.get("MEMBER_ID")
        if member_id:
            hints["member_id"] = str(member_id)[:64]
        app_token = auth.get("application_token") or auth.get("APP_SID") or auth.get("APPLICATION_TOKEN")
        if app_token:
            hints["application_token"] = str(app_token)[:128]
    return hints

def _resolve_portal(
    db: Session,
    member_id: str | None,
    application_token: str | None,
    domain: str | None,
    referer: str | None,
    origin: str | None,
) -> tuple[str | None, int | None, str | None]:
    member_id_clean = (member_id or "").strip() or None
    app_token_clean = (application_token or "").strip() or None
    domain_clean = None
    if domain:
        domain_clean = (domain or "").replace("https://", "").replace("http://", "").rstrip("/").split("/")[0] or None
    if not domain_clean:
        for raw in (referer, origin):
            if not raw:
                continue
            try:
                cand = raw.replace("https://", "").replace("http://", "").rstrip("/").split("/")[0]
                if cand and "." in cand:
                    domain_clean = cand
                    break
            except Exception:
                pass

    portal = None
    if member_id_clean:
        portal = db.execute(select(Portal).where(Portal.member_id == member_id_clean)).scalar_one_or_none()
    if not portal and app_token_clean:
        portal = db.execute(select(Portal).where(Portal.application_token == app_token_clean)).scalar_one_or_none()
    if not portal and domain_clean:
        portal = db.execute(select(Portal).where(Portal.domain == domain_clean)).scalar_one_or_none()

    if portal:
        # Update domain/member_id/application_token if missing or changed
        changed = False
        if domain_clean and portal.domain != domain_clean:
            portal.domain = domain_clean
            changed = True
        if member_id_clean and portal.member_id != member_id_clean:
            portal.member_id = member_id_clean
            changed = True
        if app_token_clean and portal.application_token != app_token_clean:
            portal.application_token = app_token_clean
            changed = True
        if changed:
            db.add(portal)
            db.commit()
        return domain_clean or portal.domain, portal.id, portal.member_id

    if member_id_clean or app_token_clean or domain_clean:
        # Create portal if we have at least one identifier
        portal = Portal(
            domain=domain_clean or "unknown.invalid",
            member_id=member_id_clean,
            application_token=app_token_clean,
            status="active",
            install_type="unknown",
        )
        db.add(portal)
        db.commit()
        db.refresh(portal)
        return domain_clean, portal.id, member_id_clean
    return None, None, None


def build_inbound_event_record(
    db: Session,
    trace_id: str | None,
    method: str,
    path: str,
    query_string: str | None,
    content_type: str | None,
    request_headers: dict,
    body_bytes: bytes,
    remote_ip: str | None,
    query_domain: str | None = None,
    settings: dict[str, Any] | None = None,
) -> BitrixInboundEvent | None:
    """Build and save one inbound event record. Does NOT run retention (caller may do it)."""
    if settings is None:
        settings = get_inbound_settings(db)
    max_body_bytes = (settings.get("max_body_kb") or DEFAULTS["max_body_kb"]) * 1024
    body_sha256 = hashlib.sha256(body_bytes).hexdigest()
    body_preview_str, body_truncated = _body_preview(body_bytes, max_body_bytes)
    parsed_redacted = None
    parsed_for_hints = None
    parsed = _parse_body_by_content_type(content_type, body_bytes)
    if isinstance(parsed, dict):
        parsed_for_hints = parsed
        if len(body_bytes) <= max_body_bytes:
            parsed_redacted = _redact_obj(parsed)
    hints = _extract_hints(parsed_for_hints)
    domain_from_payload = None
    if parsed_for_hints:
        auth = parsed_for_hints.get("auth")
        if isinstance(auth, dict):
            domain_from_payload = (auth.get("domain") or auth.get("DOMAIN") or "").strip() or None
    if not domain_from_payload and query_domain:
        domain_from_payload = (query_domain or "").strip() or None
    referer = request_headers.get("referer") or request_headers.get("Referer")
    origin = request_headers.get("origin") or request_headers.get("Origin")
    member_id = hints.get("member_id") if hints else None
    application_token = hints.get("application_token") if hints else None
    domain, portal_id, member_id_resolved = _resolve_portal(
        db,
        member_id=str(member_id) if member_id is not None else None,
        application_token=str(application_token) if application_token is not None else None,
        domain=domain_from_payload,
        referer=referer,
        origin=origin,
    )
    headers_safe = _safe_headers(request_headers)
    try:
        headers_json = json.loads(json.dumps(headers_safe, ensure_ascii=False))
    except Exception:
        headers_json = dict(headers_safe)
    rec = BitrixInboundEvent(
        trace_id=trace_id,
        portal_id=portal_id,
        domain=domain,
        member_id=member_id_resolved,
        dialog_id=str(hints.get("dialog_id"))[:128] if hints and hints.get("dialog_id") is not None else None,
        user_id=str(hints.get("user_id"))[:64] if hints and hints.get("user_id") is not None else None,
        event_name=str(hints.get("event_name"))[:128] if hints and hints.get("event_name") is not None else None,
        remote_ip=remote_ip,
        method=method,
        path=path,
        query=query_string[:2048] if query_string else None,
        content_type=content_type[:256] if content_type else None,
        headers_json=headers_json,
        body_preview=body_preview_str,
        body_truncated=body_truncated,
        body_sha256=body_sha256,
        parsed_redacted_json=parsed_redacted,
        hints_json=hints,
        status_hint="ok_logged",
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def run_retention(db: Session, settings: dict[str, Any] | None = None) -> None:
    """Delete old records: TTL retention_days and cap global max_rows (from DB settings)."""
    from datetime import datetime, timedelta
    if settings is None:
        settings = get_inbound_settings(db)
    retention_days = settings.get("retention_days") or DEFAULTS["retention_days"]
    max_rows = settings.get("max_rows") or DEFAULTS["max_rows"]
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    try:
        db.execute(delete(BitrixInboundEvent).where(BitrixInboundEvent.created_at < cutoff))
        db.commit()
    except Exception as e:
        logger.warning("bitrix_inbound_events retention TTL delete failed: %s", e)
        db.rollback()
    try:
        total = db.execute(select(func.count(BitrixInboundEvent.id))).scalar() or 0
        if total > max_rows:
            subq = select(BitrixInboundEvent.id).order_by(BitrixInboundEvent.created_at.asc()).limit(total - max_rows)
            ids_to_del = [r[0] for r in db.execute(subq).fetchall()]
            if ids_to_del:
                db.execute(delete(BitrixInboundEvent).where(BitrixInboundEvent.id.in_(ids_to_del)))
                db.commit()
    except Exception as e:
        logger.warning("bitrix_inbound_events retention max_rows delete failed: %s", e)
        db.rollback()


def get_usage(db: Session, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return used_mb, target_budget_mb, percent, approx_rows, oldest_at, newest_at."""
    if settings is None:
        settings = get_inbound_settings(db)
    target_mb = settings.get("target_budget_mb") or DEFAULTS["target_budget_mb"]
    try:
        size_row = db.execute(text("SELECT pg_total_relation_size('bitrix_inbound_events') AS bytes")).fetchone()
        bytes_used = size_row[0] if size_row and size_row[0] is not None else 0
    except Exception:
        bytes_used = 0
    used_mb = round(bytes_used / (1024 * 1024), 2)
    percent = min(100, round(used_mb / target_mb * 100)) if target_mb else 0
    try:
        approx_row = db.execute(text(
            "SELECT reltuples::bigint FROM pg_class WHERE relname = 'bitrix_inbound_events'"
        )).fetchone()
        approx_rows = int(approx_row[0]) if approx_row and approx_row[0] is not None else 0
    except Exception:
        approx_rows = 0
    try:
        minmax = db.execute(
            select(func.min(BitrixInboundEvent.created_at), func.max(BitrixInboundEvent.created_at))
        ).fetchone()
        oldest_at = minmax[0].isoformat() if minmax and minmax[0] else None
        newest_at = minmax[1].isoformat() if minmax and minmax[1] else None
    except Exception:
        oldest_at = newest_at = None
    return {
        "used_mb": used_mb,
        "target_budget_mb": target_mb,
        "percent": percent,
        "approx_rows": approx_rows,
        "oldest_at": oldest_at,
        "newest_at": newest_at,
    }


def run_prune(
    db: Session,
    mode: str,
    older_than_days: int | None = None,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Prune: auto (retention+max_rows), all (delete all), older_than_days. Returns deleted_rows, remaining_rows, used_mb_after."""
    from datetime import datetime, timedelta
    if settings is None:
        settings = get_inbound_settings(db)
    target_mb = settings.get("target_budget_mb") or DEFAULTS["target_budget_mb"]
    deleted = 0
    if mode == "all":
        try:
            r = db.execute(delete(BitrixInboundEvent))
            deleted = r.rowcount if hasattr(r, "rowcount") else 0
            db.commit()
        except Exception as e:
            logger.warning("bitrix_inbound_events prune all failed: %s", e)
            db.rollback()
    elif mode == "older_than_days" and older_than_days is not None and older_than_days >= 1:
        cutoff = datetime.utcnow() - timedelta(days=older_than_days)
        try:
            r = db.execute(delete(BitrixInboundEvent).where(BitrixInboundEvent.created_at < cutoff))
            deleted = r.rowcount if hasattr(r, "rowcount") else 0
            db.commit()
        except Exception as e:
            logger.warning("bitrix_inbound_events prune older_than_days failed: %s", e)
            db.rollback()
    elif mode == "auto":
        retention_days = settings.get("retention_days") or DEFAULTS["retention_days"]
        max_rows = settings.get("max_rows") or DEFAULTS["max_rows"]
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        try:
            r = db.execute(delete(BitrixInboundEvent).where(BitrixInboundEvent.created_at < cutoff))
            deleted += r.rowcount if hasattr(r, "rowcount") else 0
            db.commit()
        except Exception as e:
            db.rollback()
        try:
            total = db.execute(select(func.count(BitrixInboundEvent.id))).scalar() or 0
            if total > max_rows:
                subq = select(BitrixInboundEvent.id).order_by(BitrixInboundEvent.created_at.asc()).limit(total - max_rows)
                ids_to_del = [r[0] for r in db.execute(subq).fetchall()]
                if ids_to_del:
                    r = db.execute(delete(BitrixInboundEvent).where(BitrixInboundEvent.id.in_(ids_to_del)))
                    deleted += r.rowcount if hasattr(r, "rowcount") else len(ids_to_del)
                db.commit()
        except Exception as e:
            db.rollback()
    remaining = db.execute(select(func.count(BitrixInboundEvent.id))).scalar() or 0
    usage = get_usage(db, settings)
    return {
        "deleted_rows": deleted,
        "remaining_rows": remaining,
        "used_mb_after": usage["used_mb"],
    }
