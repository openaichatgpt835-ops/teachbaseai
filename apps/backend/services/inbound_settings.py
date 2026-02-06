"""Global settings for inbound events storage (from DB, not .env)."""
from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.backend.models.app_setting import AppSetting

KEY = "inbound_events"

DEFAULTS = {
    "retention_days": 3,
    "max_rows": 5000,
    "max_body_kb": 128,
    "enabled": True,
    "auto_prune_on_write": True,
    "target_budget_mb": 200,
}

VALIDATION = {
    "retention_days": (1, 30),
    "max_rows": (100, 50000),
    "max_body_kb": (1, 512),
    "target_budget_mb": (10, 2000),
}


def get_inbound_settings(db: Session) -> dict[str, Any]:
    """Return current inbound-events settings (merged with defaults)."""
    row = db.execute(select(AppSetting).where(AppSetting.key == KEY)).scalar_one_or_none()
    if not row:
        return dict(DEFAULTS)
    raw = row.value_json if hasattr(row, "value_json") else None
    if not isinstance(raw, dict):
        return dict(DEFAULTS)
    out = dict(DEFAULTS)
    for k in DEFAULTS:
        if k in raw:
            out[k] = raw[k]
    return out


def put_inbound_settings(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and save inbound-events settings. Returns saved settings."""
    from datetime import datetime
    merged = get_inbound_settings(db)
    for k, v in payload.items():
        if k not in DEFAULTS:
            continue
        if k == "enabled" or k == "auto_prune_on_write":
            merged[k] = bool(v)
            continue
        if k in VALIDATION:
            lo, hi = VALIDATION[k]
            try:
                n = int(v)
                merged[k] = max(lo, min(hi, n))
            except (TypeError, ValueError):
                pass
    row = db.execute(select(AppSetting).where(AppSetting.key == KEY)).scalar_one_or_none()
    if row:
        row.value_json = merged
        row.updated_at = datetime.utcnow()
    else:
        db.add(AppSetting(key=KEY, value_json=merged, updated_at=datetime.utcnow()))
    db.commit()
    return merged
