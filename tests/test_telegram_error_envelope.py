"""Telegram router error envelope tests."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from apps.backend.main import app
from apps.backend.deps import get_db
from apps.backend.database import Base, get_test_engine

client = TestClient(app)


@pytest.fixture
def test_db_session():
    engine = get_test_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def override_get_db(test_db_session):
    def _get_db():
        try:
            yield test_db_session
        finally:
            pass
    return _get_db


@pytest.mark.timeout(10)
def test_telegram_forbidden_returns_error_envelope(override_get_db):
    app.dependency_overrides[get_db] = override_get_db
    try:
        r = client.post("/v1/telegram/staff/999/bad-secret", json={"update_id": 1})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 403
    data = r.json()
    assert data.get("error") == "forbidden"
    assert data.get("code") == "forbidden"
    assert data.get("message") == "forbidden"
    assert "trace_id" in data
