"""Contract: /install/complete via XHR returns JSON (not HTML redirect)."""
from fastapi.testclient import TestClient

from apps.backend.main import app

client = TestClient(app)


def test_install_complete_xhr_json_ok():
    r = client.post(
        "/v1/bitrix/install/complete",
        json={"auth": {"domain": "example.bitrix24.ru"}},
        headers={
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        },
        follow_redirects=False,
    )
    assert r.status_code != 500
    ct = r.headers.get("content-type", "")
    assert ct.startswith("application/json")
