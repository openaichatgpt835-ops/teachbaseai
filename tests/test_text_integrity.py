from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_check_module():
    root = Path(__file__).resolve().parents[1]
    module_path = root / "scripts" / "check_text_integrity.py"
    spec = importlib.util.spec_from_file_location("check_text_integrity", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_text_integrity_guard_passes() -> None:
    module = _load_check_module()
    errors = module.walk()
    assert errors == [], f"text integrity violations found: {errors}"
