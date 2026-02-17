"""Unified error envelope for XHR API paths."""
import pytest
from fastapi.testclient import TestClient

from apps.backend.main import app

client = TestClient(app)


@pytest.mark.timeout(10)
def test_xhr_web_404_uses_error_envelope():
    r = client.get(
        "/v1/web/does-not-exist",
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
        },
    )
    assert r.status_code == 404
    data = r.json()
    assert data.get("code") == "http_error"
    assert data.get("error") == "http_error"
    assert "trace_id" in data
    assert "message" in data


@pytest.mark.timeout(10)
def test_xhr_telegram_404_uses_error_envelope():
    r = client.get(
        "/v1/telegram/does-not-exist",
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
        },
    )
    assert r.status_code == 404
    data = r.json()
    assert data.get("code") == "http_error"
    assert data.get("error") == "http_error"
    assert "trace_id" in data

