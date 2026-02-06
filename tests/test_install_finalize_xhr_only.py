"""Contract: install finalize is XHR-only and never returns JSON for document mode."""
from fastapi.testclient import TestClient

from apps.backend.main import app
from apps.backend.auth import create_portal_token

client = TestClient(app)


def test_install_finalize_document_mode_redirect():
    """Without X-Requested-With, document mode -> 303 redirect, not JSON."""
    r = client.post(
        "/v1/bitrix/install/finalize",
        json={"portal_id": 1, "selected_user_ids": [1], "auth_context": {}},
        headers={
            "Accept": "text/html",
            "Sec-Fetch-Dest": "iframe",
            "Sec-Fetch-Mode": "navigate",
            "Authorization": "Bearer " + create_portal_token(1, expires_minutes=15),
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    ct = r.headers.get("content-type", "")
    assert "application/json" not in ct
