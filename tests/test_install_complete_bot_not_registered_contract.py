"""XHR install/complete: when ensure_bot returns error, response is JSON with trace_id + error_code + error_description_safe."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from apps.backend.main import app

client = TestClient(app)


@pytest.mark.timeout(15)
def test_install_complete_bot_error_returns_json_with_trace_id_and_error():
    """When ensure_bot_registered returns error (e.g. bot_not_registered), response is JSON with trace_id, error_code, error_description_safe."""
    def fake_ensure_bot(db, portal_id, trace_id, **kwargs):
        return {
            "ok": False,
            "bot_id": None,
            "application_token_present": False,
            "error_code": "EVENT_URL_INVALID",
            "error_detail_safe": "Event handler URL is not accessible",
            "event_urls_sent": ["https://example.com/api/v1/bitrix/events"],
        }

    with patch("apps.backend.routers.bitrix.ensure_bot_registered", side_effect=fake_ensure_bot):
        r = client.post(
            "/v1/bitrix/install/complete",
            json={
                "auth": {"domain": "test.bitrix24.ru"},
                "AUTH_ID": "stub_token",
                "REFRESH_ID": "stub_refresh",
            },
            headers={
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/json",
            },
            follow_redirects=False,
        )
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "application/json" in ct
    data = r.json()
    assert "trace_id" in data or r.headers.get("X-Trace-Id")
    trace_id = data.get("trace_id") or r.headers.get("X-Trace-Id")
    assert trace_id
    assert "bot" in data
    bot = data["bot"]
    assert bot.get("error_code") == "EVENT_URL_INVALID"
    assert "error_detail_safe" in bot or "error_description_safe" in bot
    err_safe = bot.get("error_detail_safe") or bot.get("error_description_safe") or ""
    assert "Event" in err_safe or "URL" in err_safe or err_safe
