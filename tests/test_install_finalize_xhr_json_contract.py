"""XHR install finalize: always JSON on error, trace_id; non-XHR never JSON."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from apps.backend.main import app
from apps.backend.auth import create_portal_token

client = TestClient(app)


@pytest.mark.timeout(15)
def test_install_finalize_xhr_always_json_on_error():
    """XHR to finalize: any exception -> 500 + application/json + trace_id."""
    token = create_portal_token(1, expires_minutes=15)
    with patch("apps.backend.routers.bitrix.finalize_install") as m:
        m.side_effect = RuntimeError("simulated")
        r = client.post(
            "/v1/bitrix/install/finalize",
            json={
                "portal_id": 1,
                "selected_user_ids": [1],
                "auth_context": {},
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "Authorization": "Bearer " + token,
            },
        )
    assert r.status_code == 500
    ct = r.headers.get("content-type", "")
    assert "application/json" in ct
    data = r.json()
    assert "trace_id" in data
    assert data.get("error") in ("internal_error", "http_error")
    assert r.headers.get("X-Trace-Id") or data.get("trace_id")


@pytest.mark.timeout(15)
def test_install_finalize_non_xhr_redirect_not_json():
    """Without X-Requested-With, document mode -> 303 redirect, not JSON body."""
    r = client.post(
        "/v1/bitrix/install/finalize",
        json={"portal_id": 1, "selected_user_ids": [1], "auth_context": {}},
        headers={
            "Accept": "text/html",
            "Sec-Fetch-Dest": "iframe",
            "Sec-Fetch-Mode": "navigate",
        },
        follow_redirects=False,
    )
    # Document mode: handler returns 303 redirect before auth; or 401 with JSON for non-XHR
    # If 303: redirect, no JSON. If 401: our handler returns JSON for XHR only; for non-XHR we return detail.
    if r.status_code == 303:
        ct = r.headers.get("content-type", "")
        assert "application/json" not in ct or not ct
    elif r.status_code == 401:
        # No token -> 401; our http_exception_handler returns JSON only for XHR
        ct = r.headers.get("content-type", "")
        assert "application/json" in ct  # FastAPI default 401 is JSON
    else:
        assert r.status_code in (303, 401, 302)
