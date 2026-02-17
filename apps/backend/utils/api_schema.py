"""API response schema negotiation helpers (legacy + v2 dual mode)."""

from __future__ import annotations

from fastapi import Request


def resolve_response_schema(request: Request | None) -> str:
    """Return requested schema version: 'legacy' (default) or 'v2'."""
    if request is None:
        return "legacy"
    qp = (request.query_params.get("schema") or "").strip().lower()
    if qp in ("v2", "2"):
        return "v2"
    hdr = (request.headers.get("X-Api-Schema") or request.headers.get("X-Response-Schema") or "").strip().lower()
    if hdr in ("v2", "2"):
        return "v2"
    return "legacy"


def is_schema_v2(request: Request | None) -> bool:
    return resolve_response_schema(request) == "v2"

