"""Unified API error envelope (compatible with legacy clients)."""
from __future__ import annotations


def error_envelope(
    *,
    code: str,
    message: str,
    trace_id: str,
    detail: str | None = None,
    legacy_error: bool = True,
) -> dict:
    out = {
        "code": code,
        "message": message,
        "trace_id": trace_id,
    }
    if detail:
        out["detail"] = detail
    # Backward compatibility: existing clients read `error`.
    if legacy_error:
        out["error"] = code
    return out

