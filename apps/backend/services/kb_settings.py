"""KB settings: GigaChat credentials stored in app_settings (encrypted)."""
from typing import Any

from sqlalchemy.orm import Session

from apps.backend.models.app_setting import AppSetting
from apps.backend.models.portal_kb_setting import PortalKBSetting
from apps.backend.services.token_crypto import encrypt_token, decrypt_token, mask_token
from apps.backend.config import get_settings


SETTINGS_KEY = "gigachat"
BOT_SETTINGS_KEY = "bot_settings"
DEFAULT_EMBEDDING_MODEL = "EmbeddingsGigaR"
DEFAULT_CHAT_MODEL = "GigaChat-2-Pro"


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
    changed = False
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
    }


def get_portal_kb_settings(db: Session, portal_id: int) -> dict[str, Any]:
    row = db.get(PortalKBSetting, portal_id)
    if not row:
        return {
            "embedding_model": DEFAULT_EMBEDDING_MODEL,
            "chat_model": DEFAULT_CHAT_MODEL,
            "api_base": "",
            "prompt_preset": "auto",
            "show_sources": True,
            "sources_format": "detailed",
            **get_portal_bot_settings(db, portal_id),
        }
    return {
        "embedding_model": row.embedding_model or DEFAULT_EMBEDDING_MODEL,
        "chat_model": row.chat_model or DEFAULT_CHAT_MODEL,
        "api_base": row.api_base or "",
        "prompt_preset": row.prompt_preset or "auto",
        "show_sources": row.show_sources if row.show_sources is not None else True,
        "sources_format": row.sources_format or "detailed",
        **get_portal_bot_settings(db, portal_id),
    }


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
    from datetime import datetime
    row.updated_at = datetime.utcnow()
    db.commit()
    return get_portal_kb_settings(db, portal_id)


def get_effective_gigachat_settings(db: Session, portal_id: int) -> dict[str, Any]:
    base = get_gigachat_settings(db)
    bot = get_bot_settings(db)
    p = get_portal_kb_settings(db, portal_id)
    # default models if global settings are empty
    if not base.get("embedding_model"):
        base["embedding_model"] = DEFAULT_EMBEDDING_MODEL
        base["model"] = DEFAULT_EMBEDDING_MODEL
    if not base.get("chat_model"):
        base["chat_model"] = DEFAULT_CHAT_MODEL
    # override models/api_base per portal if provided
    if p.get("embedding_model"):
        base["embedding_model"] = p["embedding_model"]
        base["model"] = p["embedding_model"]
    if p.get("chat_model"):
        base["chat_model"] = p["chat_model"]
    if p.get("api_base"):
        base["api_base"] = p["api_base"]
    base["prompt_preset"] = p.get("prompt_preset") or "auto"
    # bot defaults + portal overrides
    base.update(bot)
    for k in (
        "temperature",
        "max_tokens",
        "top_p",
        "presence_penalty",
        "frequency_penalty",
        "allow_general",
        "strict_mode",
        "context_messages",
        "context_chars",
        "retrieval_top_k",
        "retrieval_max_chars",
        "lex_boost",
        "use_history",
        "use_cache",
        "system_prompt_extra",
        "show_sources",
        "sources_format",
    ):
        if p.get(k) is not None:
            base[k] = p.get(k)
    base["portal_override"] = p
    return base


def set_gigachat_settings(
    db: Session,
    api_base: str | None,
    model: str | None,
    embedding_model: str | None,
    chat_model: str | None,
    client_id: str | None,
    auth_key: str | None,
    scope: str | None,
    client_secret: str | None,
    access_token: str | None,
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
        import time
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
