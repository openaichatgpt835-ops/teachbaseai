"""Тест: /install/complete при document mode НИКОГДА не отдаёт JSON.

Контракт: при открытии install/complete как документ (form submit, navigation)
ответ — 303 redirect на /install или 200 HTML, но НЕ application/json.
"""
import pytest
from fastapi.testclient import TestClient

from apps.backend.main import app

client = TestClient(app)


class TestInstallCompleteDocumentMode:
    """Document mode — редирект или HTML, не JSON."""

    def test_install_complete_document_mode_never_json(self):
        """POST без X-Requested-With, Accept:text/html — не JSON."""
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
            assert "/install" in loc
        elif r.status_code == 200:
            assert "text/html" in ct
