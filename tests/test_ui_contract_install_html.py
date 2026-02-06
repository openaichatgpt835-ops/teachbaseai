"""Contract: GET /v1/bitrix/install must always return HTML UI; install.html safe JSON parse."""
from pathlib import Path

from fastapi.testclient import TestClient

from apps.backend.main import app

client = TestClient(app)

INSTALL_HTML_PATH = Path(__file__).resolve().parent.parent / "apps" / "backend" / "templates" / "install.html"


def test_install_html_contract():
    r = client.get("/v1/bitrix/install", headers={"Accept": "text/html"})
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "text/html" in ct
    assert r.headers.get("x-teachbase-ui") == "1"
    assert not r.text.strip().startswith("{")


def test_install_html_fetch_wrapper_no_unexpected_token():
    """install.html must not call .json() without content-type check (avoids 'Unexpected token' on 500)."""
    content = INSTALL_HTML_PATH.read_text(encoding="utf-8")
    assert "parseJsonOrThrow" in content or "application/json" in content
    # Finalize fetch must use parseJsonOrThrow (no raw r.json())
    assert "parseJsonOrThrow(r)" in content
    # No raw r.json() or ur.json() without prior content-type check
    assert "ct.indexOf('application/json')" in content or "ctComplete.indexOf" in content
