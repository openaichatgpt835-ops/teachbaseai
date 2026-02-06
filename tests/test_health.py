"""Тесты health endpoints."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from apps.backend.main import app
    return TestClient(app)


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"
