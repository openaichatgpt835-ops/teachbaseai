"""Contract: GET /v1/bitrix/handler must always return HTML UI."""
from fastapi.testclient import TestClient

from apps.backend.main import app

client = TestClient(app)


def test_handler_html_contract():
    r = client.get("/v1/bitrix/handler", headers={"Accept": "text/html"})
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "text/html" in ct
    assert r.headers.get("x-teachbase-ui") == "1"
    body = r.text
    assert not body.strip().startswith("{")
    assert (
        "Доступ" in body
        or "Сохранить доступ" in body
        or "Выбрать пользователей" in body
    )
    assert "access-users-ui" in body
    assert "portal_token" not in body
    assert "\"status\":\"ok\"" not in body
    assert "portal_id" not in body
