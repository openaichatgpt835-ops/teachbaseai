"""Тест: GET /v1/bitrix/handler ВСЕГДА возвращает HTML UI, НИКОГДА JSON.

Контракт: iframe при открытии установленного приложения в Bitrix24 грузит handler URL.
Ответ ДОЛЖЕН быть text/html с UI (секция Доступ, список пользователей).
"""
import pytest
from fastapi.testclient import TestClient

from apps.backend.main import app

client = TestClient(app)

HANDLER_PATH = "/v1/bitrix/handler"


class TestHandlerReturnsHtml:
    """GET /handler всегда text/html с UI."""

    def test_handler_returns_html_not_json(self):
        """GET /handler с Accept:text/html — 200, text/html, тело НЕ JSON."""
        r = client.get(HANDLER_PATH, headers={"Accept": "text/html"})
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert "text/html" in ct
        body = r.text
        assert not body.strip().startswith("{")
        assert "access-users-ui" in body
        assert "Доступ" in body or "Сохранить доступ" in body or "Выбрать пользователей" in body

    def test_handler_never_exposes_portal_token(self):
        """GET /handler не содержит portal_token в теле (защита от утечек)."""
        r = client.get(HANDLER_PATH, headers={"Accept": "text/html"})
        body = r.text
        assert "portal_token" not in body
        assert "\"status\":\"ok\"" not in body
        assert "portal_id" not in body
