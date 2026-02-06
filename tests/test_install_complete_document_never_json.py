"""Contract: /install/complete in document mode must never return JSON."""
from fastapi.testclient import TestClient

from apps.backend.main import app

client = TestClient(app)


def test_install_complete_document_mode_never_json():
    r = client.post(
        "/v1/bitrix/install/complete",
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303, 200)
    ct = r.headers.get("content-type", "")
    assert "application/json" not in ct
    if r.status_code in (302, 303):
        loc = r.headers.get("location", "")
        assert "/bitrix/install" in loc or "/bitrix/handler" in loc
    else:
        assert "text/html" in ct
