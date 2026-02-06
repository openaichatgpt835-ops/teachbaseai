"""Тест: /install/complete НЕ должен возвращать JSON при document navigation."""
import pytest
from fastapi.testclient import TestClient

from apps.backend.main import app

client = TestClient(app)


class TestInstallCompleteNoJsonInIframe:
    """Проверяем, что /install/complete не отдаёт JSON, когда запрос идёт как документ."""

    def test_get_returns_303_redirect(self):
        """GET /install/complete всегда редирект на /install."""
        r = client.get("/v1/bitrix/install/complete", follow_redirects=False)
        assert r.status_code == 303
        assert "/install" in r.headers.get("location", "")
        assert r.text == "" or "status" not in r.text.lower()

    def test_post_without_xhr_header_returns_303(self):
        """POST без X-Requested-With — редирект, не JSON."""
        r = client.post(
            "/v1/bitrix/install/complete",
            data={"domain": "test.bitrix24.ru"},
            headers={"Accept": "application/json"},
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert "/install" in r.headers.get("location", "")

    def test_post_with_sec_fetch_dest_iframe_returns_303(self):
        """POST с Sec-Fetch-Dest: iframe — редирект, не JSON."""
        r = client.post(
            "/v1/bitrix/install/complete",
            json={"auth": {"domain": "test.bitrix24.ru"}},
            headers={
                "Accept": "application/json",
                "Sec-Fetch-Dest": "iframe",
            },
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert "/install" in r.headers.get("location", "")

    def test_post_with_sec_fetch_dest_document_returns_303(self):
        """POST с Sec-Fetch-Dest: document — редирект, не JSON."""
        r = client.post(
            "/v1/bitrix/install/complete",
            json={"auth": {"domain": "test.bitrix24.ru"}},
            headers={
                "Accept": "application/json",
                "Sec-Fetch-Dest": "document",
            },
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert "/install" in r.headers.get("location", "")

    def test_post_form_urlencoded_without_xhr_returns_303(self):
        """POST form-urlencoded без X-Requested-With — редирект (типичный form submit)."""
        r = client.post(
            "/v1/bitrix/install/complete",
            data={"AUTH_ID": "xxx", "DOMAIN": "test.bitrix24.ru"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert "/install" in r.headers.get("location", "")

    def test_post_with_xhr_header_returns_json(self):
        """POST с X-Requested-With: XMLHttpRequest — JSON (наш fetch из install.html)."""
        r = client.post(
            "/v1/bitrix/install/complete",
            json={"auth": {"domain": "test.bitrix24.ru"}},
            headers={
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            },
            follow_redirects=False,
        )
        # Либо 400 (missing access_token), либо 200 — но это JSON, не редирект
        assert r.status_code in (200, 400)
        assert r.headers.get("content-type", "").startswith("application/json")
        data = r.json()
        assert "error" in data or "status" in data

    def test_bitrix_typical_install_post_returns_303(self):
        """
        Типичный POST от Bitrix24 при установке:
        - Content-Type: application/x-www-form-urlencoded
        - Нет X-Requested-With
        - Accept может быть любым
        Должен вернуть 303, не JSON.
        """
        r = client.post(
            "/v1/bitrix/install/complete",
            data={
                "AUTH_ID": "abc123",
                "REFRESH_ID": "xyz789",
                "DOMAIN": "myportal.bitrix24.ru",
                "MEMBER_ID": "member123",
                "APP_SID": "app_sid_value",
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            follow_redirects=False,
        )
        assert r.status_code == 303, f"Expected 303, got {r.status_code}: {r.text}"
        assert "/install" in r.headers.get("location", "")

    def test_never_json_body_without_xhr(self):
        """Без X-Requested-With тело ответа не должно содержать JSON."""
        r = client.post(
            "/v1/bitrix/install/complete",
            json={"auth": {"domain": "test.bitrix24.ru", "access_token": "xxx"}},
            headers={"Accept": "application/json"},
            follow_redirects=False,
        )
        assert r.status_code == 303
        # Тело должно быть пустым (редирект)
        assert r.text == "" or "portal_id" not in r.text
