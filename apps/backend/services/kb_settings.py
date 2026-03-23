"""KB settings: GigaChat credentials stored in app_settings (encrypted)."""
from typing import Any
import time

from sqlalchemy.orm import Session

from apps.backend.models.app_setting import AppSetting
from apps.backend.models.portal_kb_setting import PortalKBSetting
from apps.backend.services.token_crypto import encrypt_token, decrypt_token, mask_token
from apps.backend.services.billing import get_portal_effective_policy
from apps.backend.config import get_settings


SETTINGS_KEY = "gigachat"
BOT_SETTINGS_KEY = "bot_settings"
DEFAULT_EMBEDDING_MODEL = "EmbeddingsGigaR"
DEFAULT_CHAT_MODEL = "GigaChat-2-Pro"


def _portal_feature_gates(db: Session, portal_id: int) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    policy = get_portal_effective_policy(db, portal_id)
    features = dict(policy.get("features") or {})

    def gate(key: str) -> dict[str, Any]:
        allowed = bool(features.get(key, True))
        return {
            "allowed": allowed,
            "reason": "" if allowed else "locked_by_tariff",
        }

    return (
        {
            "model_selection": gate("allow_model_selection"),
            "advanced_model_tuning": gate("allow_advanced_model_tuning"),
            "media_transcription": gate("allow_media_transcription"),
            "speaker_diarization": gate("allow_speaker_diarization"),
        },
        policy,
    )


def _enc_key() -> str:
    s = get_settings()
    return s.token_encryption_key if s.token_encryption_key else s.secret_key


def get_gigachat_settings(db: Session) -> dict[str, Any]:
    row = db.get(AppSetting, SETTINGS_KEY)
    if not row:
        return {
            "api_base": "",
            "model": "",
            "embedding_model": "",
            "chat_model": "",
            "has_client_id": False,
            "has_auth_key": False,
            "scope": "",
            "has_access_token": False,
            "access_token_expires_at": None,
        }
    data = row.value_json or {}
    client_id = data.get("client_id") or ""
    auth_key_enc = data.get("auth_key_enc") or data.get("client_secret_enc") or ""
    access_token_enc = data.get("access_token_enc") or ""
    auth_key_plain = decrypt_token(auth_key_enc, _enc_key()) if auth_key_enc else ""
    legacy_model = (data.get("model") or "").strip()
    embedding_model = (data.get("embedding_model") or "").strip() or legacy_model
    chat_model = (data.get("chat_model") or "").strip()
    # auto-upgrade old defaults to new defaults
    old_embed = {"Embeddings-2", "embeddings-2", ""}
    old_chat = {"GigaChat-2", "gigachat-2", ""}
    changed = False
    if embedding_model in old_embed:
        embedding_model = DEFAULT_EMBEDDING_MODEL
        data["embedding_model"] = DEFAULT_EMBEDDING_MODEL
        if legacy_model in old_embed:
            data["model"] = DEFAULT_EMBEDDING_MODEL
        changed = True
    if chat_model in old_chat:
        chat_model = DEFAULT_CHAT_MODEL
        data["chat_model"] = DEFAULT_CHAT_MODEL
        changed = True
    # normalize ms -> seconds for stored expires_at
    exp = data.get("access_token_expires_at")
    if isinstance(exp, int) and exp > 10**11:
        exp = int(exp / 1000)
        data["access_token_expires_at"] = exp
        changed = True
    if changed:
        row.value_json = dict(data)
        db.commit()
    return {
        "api_base": data.get("api_base") or "",
        "model": legacy_model,
        "embedding_model": embedding_model,
        "chat_model": chat_model,
        "scope": data.get("scope") or "",
        "has_client_id": bool(client_id),
        "has_auth_key": bool(auth_key_enc),
        "has_access_token": bool(access_token_enc),
        "access_token_expires_at": data.get("access_token_expires_at"),
        "client_id_masked": mask_token(client_id) if client_id else "",
        "auth_key_masked": mask_token(auth_key_plain) if auth_key_plain else "",
    }


def get_gigachat_health_snapshot(db: Session) -> dict[str, Any]:
    from apps.backend.services.gigachat_client import request_access_token_detailed

    settings = get_gigachat_settings(db)
    auth_key = (get_gigachat_auth_key_plain(db) or "").strip()
    access_token = (get_gigachat_access_token_plain(db) or "").strip()
    scope = (settings.get("scope") or "").strip()
    now_ts = int(time.time())
    exp = settings.get("access_token_expires_at")
    expires_at = int(exp) if isinstance(exp, int) else 0
    token_ttl = (expires_at - now_ts) if expires_at else None
    token_is_expired = bool(expires_at and expires_at <= now_ts)

    probe_status = None
    probe_error = None
    probe_ok = False
    probe_expires_at = None
    if auth_key and scope:
        _tok, probe_expires_at, probe_error, probe_status = request_access_token_detailed(auth_key, scope)
        probe_ok = bool(_tok)

    health_status = "ok"
    issues: list[str] = []
    if not auth_key:
        health_status = "broken"
        issues.append("missing_auth_key")
    if not scope:
        health_status = "broken"
        issues.append("missing_scope")
    if auth_key and scope and not probe_ok:
        health_status = "broken"
        issues.append(f"oauth_probe_failed:{probe_error or probe_status or 'unknown'}")
    if access_token and token_is_expired:
        if health_status != "broken":
            health_status = "warning"
        issues.append("access_token_expired")
    if access_token and not auth_key:
        health_status = "broken"
        issues.append("orphan_access_token")
    if not access_token and auth_key and scope and probe_ok:
        if health_status != "broken":
            health_status = "warning"
        issues.append("missing_cached_access_token")

    can_refresh = bool(auth_key and scope)
    return {
        "status": health_status,
        "issues": issues,
        "has_auth_key": bool(auth_key),
        "auth_key_len": len(auth_key),
        "has_scope": bool(scope),
        "scope": scope,
        "has_access_token": bool(access_token),
        "access_token_expires_at": expires_at or None,
        "access_token_ttl_sec": token_ttl,
        "token_is_expired": token_is_expired,
        "can_refresh": can_refresh,
        "oauth_probe": {
            "attempted": bool(auth_key and scope),
            "ok": probe_ok,
            "status": probe_status,
            "error": probe_error,
            "expires_at": probe_expires_at,
        },
    }


def get_bot_settings(db: Session) -> dict[str, Any]:
    row = db.get(AppSetting, BOT_SETTINGS_KEY)
    data = dict(row.value_json or {}) if row else {}
    return {
        "temperature": float(data.get("temperature") or 0.2),
        "max_tokens": int(data.get("max_tokens") or 700),
        "top_p": data.get("top_p"),
        "presence_penalty": data.get("presence_penalty"),
        "frequency_penalty": data.get("frequency_penalty"),
        "allow_general": bool(data.get("allow_general")) if data.get("allow_general") is not None else False,
        "strict_mode": bool(data.get("strict_mode")) if data.get("strict_mode") is not None else True,
        "context_messages": int(data.get("context_messages") or 6),
        "context_chars": int(data.get("context_chars") or 4000),
        "retrieval_top_k": int(data.get("retrieval_top_k") or 5),
        "retrieval_max_chars": int(data.get("retrieval_max_chars") or 4000),
        "lex_boost": float(data.get("lex_boost") or 0.12),
        "use_history": bool(data.get("use_history")) if data.get("use_history") is not None else True,
        "use_cache": bool(data.get("use_cache")) if data.get("use_cache") is not None else True,
        "system_prompt_extra": (data.get("system_prompt_extra") or ""),
        "show_sources": bool(data.get("show_sources")) if data.get("show_sources") is not None else True,
        "sources_format": (data.get("sources_format") or "detailed"),
        "collections_multi_assign": bool(data.get("collections_multi_assign")) if data.get("collections_multi_assign") is not None else True,
        "smart_folder_threshold": int(data.get("smart_folder_threshold") or 5),
    }


def set_bot_settings(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    row = db.get(AppSetting, BOT_SETTINGS_KEY)
    data = dict(row.value_json or {}) if row else {}
    for k, v in payload.items():
        data[k] = v
    if not row:
        row = AppSetting(key=BOT_SETTINGS_KEY, value_json=data)
        db.add(row)
    else:
        row.value_json = dict(data)
    db.commit()
    return get_bot_settings(db)


def get_portal_bot_settings(db: Session, portal_id: int) -> dict[str, Any]:
    row = db.get(PortalKBSetting, portal_id)
    if not row:
        return {
            "temperature": None,
            "max_tokens": None,
            "top_p": None,
            "presence_penalty": None,
            "frequency_penalty": None,
            "allow_general": None,
            "strict_mode": None,
            "context_messages": None,
            "context_chars": None,
            "retrieval_top_k": None,
            "retrieval_max_chars": None,
            "lex_boost": None,
            "use_history": None,
            "use_cache": None,
            "system_prompt_extra": None,
            "media_transcription_enabled": None,
            "speaker_diarization_enabled": None,
            "collections_multi_assign": None,
            "smart_folder_threshold": None,
        }
    return {
        "temperature": row.temperature,
        "max_tokens": row.max_tokens,
        "top_p": row.top_p,
        "presence_penalty": row.presence_penalty,
        "frequency_penalty": row.frequency_penalty,
        "allow_general": row.allow_general,
        "strict_mode": row.strict_mode,
        "context_messages": row.context_messages,
        "context_chars": row.context_chars,
        "retrieval_top_k": row.retrieval_top_k,
        "retrieval_max_chars": row.retrieval_max_chars,
        "lex_boost": row.lex_boost,
        "use_history": row.use_history,
        "use_cache": row.use_cache,
        "system_prompt_extra": row.system_prompt_extra,
        "media_transcription_enabled": row.media_transcription_enabled,
        "speaker_diarization_enabled": row.speaker_diarization_enabled,
        "collections_multi_assign": row.collections_multi_assign,
        "smart_folder_threshold": row.smart_folder_threshold,
    }


def get_portal_kb_settings(db: Session, portal_id: int) -> dict[str, Any]:
    row = db.get(PortalKBSetting, portal_id)
    if not row:
        out = {
            "embedding_model": DEFAULT_EMBEDDING_MODEL,
            "chat_model": DEFAULT_CHAT_MODEL,
            "api_base": "",
            "prompt_preset": "auto",
            "show_sources": True,
            "sources_format": "detailed",
            "media_transcription_enabled": True,
            "speaker_diarization_enabled": False,
            "collections_multi_assign": True,
            "smart_folder_threshold": 5,
            **get_portal_bot_settings(db, portal_id),
        }
    else:
        out = {
        "embedding_model": row.embedding_model or DEFAULT_EMBEDDING_MODEL,
        "chat_model": row.chat_model or DEFAULT_CHAT_MODEL,
        "api_base": row.api_base or "",
        "prompt_preset": row.prompt_preset or "auto",
        "show_sources": row.show_sources if row.show_sources is not None else True,
        "sources_format": row.sources_format or "detailed",
        "media_transcription_enabled": row.media_transcription_enabled if row.media_transcription_enabled is not None else True,
        "speaker_diarization_enabled": row.speaker_diarization_enabled if row.speaker_diarization_enabled is not None else False,
        "collections_multi_assign": row.collections_multi_assign if row.collections_multi_assign is not None else True,
        "smart_folder_threshold": row.smart_folder_threshold if row.smart_folder_threshold is not None else 5,
        **get_portal_bot_settings(db, portal_id),
    }
    gates, policy = _portal_feature_gates(db, portal_id)
    out["feature_gates"] = gates
    out["billing_policy"] = {
        "account_id": policy.get("account_id"),
        "plan_code": policy.get("plan_code"),
        "plan_name": (policy.get("plan") or {}).get("name") if policy.get("plan") else None,
        "source": policy.get("source"),
    }
    if not gates["media_transcription"]["allowed"]:
        out["media_transcription_enabled"] = False
        out["speaker_diarization_enabled"] = False
    elif not gates["speaker_diarization"]["allowed"]:
        out["speaker_diarization_enabled"] = False
    return out


def set_portal_kb_settings(
    db: Session,
    portal_id: int,
    embedding_model: str | None,
    chat_model: str | None,
    api_base: str | None,
    prompt_preset: str | None = None,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    top_p: float | None = None,
    presence_penalty: float | None = None,
    frequency_penalty: float | None = None,
    allow_general: bool | None = None,
    strict_mode: bool | None = None,
    context_messages: int | None = None,
    context_chars: int | None = None,
    retrieval_top_k: int | None = None,
    retrieval_max_chars: int | None = None,
    lex_boost: float | None = None,
    use_history: bool | None = None,
    use_cache: bool | None = None,
    system_prompt_extra: str | None = None,
    show_sources: bool | None = None,
    sources_format: str | None = None,
    media_transcription_enabled: bool | None = None,
    speaker_diarization_enabled: bool | None = None,
    collections_multi_assign: bool | None = None,
    smart_folder_threshold: int | None = None,
) -> dict[str, Any]:
    row = db.get(PortalKBSetting, portal_id)
    if not row:
        row = PortalKBSetting(portal_id=portal_id)
        db.add(row)
    if embedding_model is not None:
        row.embedding_model = (embedding_model or "").strip() or None
    if chat_model is not None:
        row.chat_model = (chat_model or "").strip() or None
    if api_base is not None:
        row.api_base = (api_base or "").strip() or None
    if prompt_preset is not None:
        row.prompt_preset = (prompt_preset or "").strip() or None
    if temperature is not None:
        row.temperature = temperature
    if max_tokens is not None:
        row.max_tokens = max_tokens
    if top_p is not None:
        row.top_p = top_p
    if presence_penalty is not None:
        row.presence_penalty = presence_penalty
    if frequency_penalty is not None:
        row.frequency_penalty = frequency_penalty
    if allow_general is not None:
        row.allow_general = allow_general
    if strict_mode is not None:
        row.strict_mode = strict_mode
    if context_messages is not None:
        row.context_messages = context_messages
    if context_chars is not None:
        row.context_chars = context_chars
    if retrieval_top_k is not None:
        row.retrieval_top_k = retrieval_top_k
    if retrieval_max_chars is not None:
        row.retrieval_max_chars = retrieval_max_chars
    if lex_boost is not None:
        row.lex_boost = lex_boost
    if use_history is not None:
        row.use_history = use_history
    if use_cache is not None:
        row.use_cache = use_cache
    if system_prompt_extra is not None:
        row.system_prompt_extra = (system_prompt_extra or "").strip() or None
    if show_sources is not None:
        row.show_sources = bool(show_sources)
    if sources_format is not None:
        row.sources_format = (sources_format or "").strip() or None
    if media_transcription_enabled is not None:
        row.media_transcription_enabled = bool(media_transcription_enabled)
    if speaker_diarization_enabled is not None:
        row.speaker_diarization_enabled = bool(speaker_diarization_enabled)
    if collections_multi_assign is not None:
        row.collections_multi_assign = bool(collections_multi_assign)
    if smart_folder_threshold is not None:
        row.smart_folder_threshold = int(smart_folder_threshold)
    from datetime import datetime
    row.updated_at = datetime.utcnow()
    db.commit()
    return get_portal_kb_settings(db, portal_id)


def get_effective_gigachat_settings(db: Session, portal_id: int) -> dict[str, Any]:
    base = get_gigachat_settings(db)
    bot = get_bot_settings(db)
    p = get_portal_kb_settings(db, portal_id)
    gates = (p.get("feature_gates") or {})
    allow_model_selection = bool((gates.get("model_selection") or {}).get("allowed", True))
    allow_advanced_tuning = bool((gates.get("advanced_model_tuning") or {}).get("allowed", True))
    # default models if global settings are empty
    if not base.get("embedding_model"):
        base["embedding_model"] = DEFAULT_EMBEDDING_MODEL
        base["model"] = DEFAULT_EMBEDDING_MODEL
    if not base.get("chat_model"):
        base["chat_model"] = DEFAULT_CHAT_MODEL
    # override models/api_base per portal if provided
    if allow_model_selection and p.get("embedding_model"):
        base["embedding_model"] = p["embedding_model"]
        base["model"] = p["embedding_model"]
    if allow_model_selection and p.get("chat_model"):
        base["chat_model"] = p["chat_model"]
    if allow_model_selection and p.get("api_base"):
        base["api_base"] = p["api_base"]
    base["prompt_preset"] = p.get("prompt_preset") or "auto"
    # bot defaults + portal overrides
    base.update(bot)
    allowed_override_keys = [
        "allow_general",
        "strict_mode",
        "use_history",
        "use_cache",
        "show_sources",
        "sources_format",
        "media_transcription_enabled",
        "speaker_diarization_enabled",
        "collections_multi_assign",
        "smart_folder_threshold",
    ]
    if allow_advanced_tuning:
        allowed_override_keys.extend(
            [
                "temperature",
                "max_tokens",
                "top_p",
                "presence_penalty",
                "frequency_penalty",
                "context_messages",
                "context_chars",
                "retrieval_top_k",
                "retrieval_max_chars",
                "lex_boost",
                "system_prompt_extra",
            ]
        )
    for k in allowed_override_keys:
        if p.get(k) is not None:
            base[k] = p.get(k)
    base["feature_gates"] = gates
    base["billing_policy"] = p.get("billing_policy")
    base["portal_override"] = p
    return base


def is_media_transcription_enabled(db: Session, portal_id: int) -> bool:
    p = get_portal_kb_settings(db, portal_id)
    val = p.get("media_transcription_enabled")
    return True if val is None else bool(val)


def is_speaker_diarization_enabled(db: Session, portal_id: int) -> bool:
    p = get_portal_kb_settings(db, portal_id)
    return bool(p.get("speaker_diarization_enabled"))


def set_gigachat_settings(
    db: Session,
    api_base: str | None,
    model: str | None,
    embedding_model: str | None = None,
    chat_model: str | None = None,
    client_id: str | None = None,
    auth_key: str | None = None,
    scope: str | None = None,
    client_secret: str | None = None,
    access_token: str | None = None,
    access_token_expires_at: int | None = None,
) -> dict[str, Any]:
    row = db.get(AppSetting, SETTINGS_KEY)
    # Всегда работаем с копией, чтобы SQLAlchemy увидел изменения JSON
    data = dict(row.value_json or {}) if row else {}
    enc = _enc_key()
    if api_base is not None:
        data["api_base"] = (api_base or "").strip()
    if model is not None:
        data["model"] = (model or "").strip()
    if embedding_model is not None:
        data["embedding_model"] = (embedding_model or "").strip()
    if chat_model is not None:
        data["chat_model"] = (chat_model or "").strip()
    if client_id is not None:
        data["client_id"] = (client_id or "").strip()
    if scope is not None:
        data["scope"] = (scope or "").strip()
    if auth_key is not None:
        data["auth_key_enc"] = encrypt_token((auth_key or "").strip(), enc) if auth_key else ""
    elif client_secret is not None:
        # backward compatibility: treat old client_secret as auth_key
        data["auth_key_enc"] = encrypt_token((client_secret or "").strip(), enc) if client_secret else ""
    if access_token is not None:
        data["access_token_enc"] = encrypt_token((access_token or "").strip(), enc) if access_token else ""
    if access_token_expires_at is not None:
        data["access_token_expires_at"] = access_token_expires_at
    if not row:
        row = AppSetting(key=SETTINGS_KEY, value_json=data)
        db.add(row)
    else:
        row.value_json = dict(data)
    db.commit()
    return get_gigachat_settings(db)


def get_gigachat_auth_key_plain(db: Session) -> str:
    row = db.get(AppSetting, SETTINGS_KEY)
    if not row or not row.value_json:
        return ""
    enc = _enc_key()
    auth_key_enc = row.value_json.get("auth_key_enc") or row.value_json.get("client_secret_enc") or ""
    return decrypt_token(auth_key_enc, enc) or ""


def get_gigachat_access_token_plain(db: Session) -> str:
    row = db.get(AppSetting, SETTINGS_KEY)
    if not row or not row.value_json:
        return ""
    enc = _enc_key()
    token_enc = row.value_json.get("access_token_enc") or ""
    return decrypt_token(token_enc, enc) or ""


def get_valid_gigachat_access_token(
    db: Session,
    skew_seconds: int = 60,
    force_refresh: bool = False,
) -> tuple[str | None, str | None]:
    data = get_gigachat_settings(db)
    token = get_gigachat_access_token_plain(db)
    expires_at = data.get("access_token_expires_at")
    scope = (data.get("scope") or "").strip()
    if force_refresh or not token:
        token, exp, err = _refresh_gigachat_token(db, scope)
        return token, err
    if expires_at and isinstance(expires_at, int):
        if expires_at > 10**11:
            # stored in ms; normalize to seconds and persist
            expires_at = int(expires_at / 1000)
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
                access_token=None,
                access_token_expires_at=expires_at,
            )
        if expires_at <= int(time.time()) + skew_seconds:
            token, exp, err = _refresh_gigachat_token(db, scope)
            return token, err
    return token, None


def _refresh_gigachat_token(db: Session, scope: str) -> tuple[str | None, int | None, str | None]:
    from apps.backend.services.gigachat_client import request_access_token
    auth_key = get_gigachat_auth_key_plain(db)
    if not auth_key:
        return None, None, "missing_auth_key"
    if not scope:
        return None, None, "missing_scope"
    token, expires_at, err = request_access_token(auth_key, scope)
    if err:
        return None, None, err
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
    return token, expires_at, None
