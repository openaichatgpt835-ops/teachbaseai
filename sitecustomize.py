"""Runtime compatibility patches for local Python environment.

This file is auto-imported by Python (if present on sys.path).
It patches known local dependency skew without touching application code.
"""

from __future__ import annotations


def _patch_pydantic_core_validate_core_schema() -> None:
    try:
        import pydantic_core  # type: ignore
    except Exception:
        return
    if hasattr(pydantic_core, "validate_core_schema"):
        return

    # Compatibility shim for older pydantic versions expecting this symbol.
    def _validate_core_schema(schema):  # noqa: ANN001
        return schema

    setattr(pydantic_core, "validate_core_schema", _validate_core_schema)


_patch_pydantic_core_validate_core_schema()

