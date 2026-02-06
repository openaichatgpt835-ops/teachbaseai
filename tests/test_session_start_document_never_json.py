"""Contract: /session/start in document mode must never return JSON."""
from fastapi.testclient import TestClient

from apps.backend.main import app

client = TestClient(app)


def test_session_start_document_mode_never_json():
    r = client.post(
        "/v1/bitrix/session/start",
        headers={
            "Accept": "text/html",
            "Sec-Fetch-Dest": "iframe",
            "Sec-Fetch-Mode": "navigate",
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303, 200)
    ct = r.headers.get("content-type", "")
    assert "application/json" not in ct
