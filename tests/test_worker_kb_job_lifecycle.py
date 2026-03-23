from datetime import datetime

import pytest
from sqlalchemy.orm import sessionmaker

from apps.backend.database import Base, get_test_engine
from apps.backend.models.kb import KBJob
from apps.backend.models.portal import Portal
from apps.worker.jobs import process_kb_job


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


@pytest.mark.timeout(10)
def test_process_kb_job_marks_duplicate_as_done(test_db_session, monkeypatch):
    portal = Portal(domain="worker-lifecycle.bitrix24.ru", status="active")
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)

    other = KBJob(
        portal_id=portal.id,
        job_type="ingest",
        status="queued",
        payload_json={"file_id": 123},
        created_at=datetime.utcnow(),
    )
    current = KBJob(
        portal_id=portal.id,
        job_type="ingest",
        status="queued",
        payload_json={"file_id": 123},
        created_at=datetime.utcnow(),
    )
    test_db_session.add(other)
    test_db_session.add(current)
    test_db_session.commit()

    SessionLocal = sessionmaker(bind=test_db_session.bind)
    monkeypatch.setattr("apps.backend.database.get_session_factory", lambda: SessionLocal)

    ok = process_kb_job(current.id)
    assert ok is True

    test_db_session.expire_all()
    refreshed = test_db_session.get(KBJob, current.id)
    assert refreshed is not None
    assert refreshed.status == "done"
    assert (refreshed.error_message or "").startswith("duplicate_skipped:")


@pytest.mark.timeout(10)
def test_process_kb_job_rate_limited_returns_to_queue(test_db_session, monkeypatch):
    portal = Portal(domain="worker-ratelimit.bitrix24.ru", status="active")
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)

    current = KBJob(
        portal_id=portal.id,
        job_type="ingest",
        status="queued",
        payload_json={"file_id": 456},
        created_at=datetime.utcnow(),
    )
    test_db_session.add(current)
    test_db_session.commit()

    SessionLocal = sessionmaker(bind=test_db_session.bind)
    monkeypatch.setattr("apps.backend.database.get_session_factory", lambda: SessionLocal)
    monkeypatch.setattr(
        "apps.backend.services.kb_ingest.ingest_file",
        lambda db, file_id, trace_id=None: {"ok": False, "error": "rate_limited"},
    )

    ok = process_kb_job(current.id)
    assert ok is False

    test_db_session.expire_all()
    refreshed = test_db_session.get(KBJob, current.id)
    assert refreshed is not None
    assert refreshed.status == "queued"
    assert refreshed.error_message == "rate_limited"


@pytest.mark.timeout(10)
def test_process_kb_job_exception_sets_error_status(test_db_session, monkeypatch):
    portal = Portal(domain="worker-exception.bitrix24.ru", status="active")
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)

    current = KBJob(
        portal_id=portal.id,
        job_type="ingest",
        status="queued",
        payload_json={"file_id": 789},
        created_at=datetime.utcnow(),
    )
    test_db_session.add(current)
    test_db_session.commit()

    SessionLocal = sessionmaker(bind=test_db_session.bind)
    monkeypatch.setattr("apps.backend.database.get_session_factory", lambda: SessionLocal)

    def _boom(db, file_id, trace_id=None):
        raise RuntimeError("boom")

    monkeypatch.setattr("apps.backend.services.kb_ingest.ingest_file", _boom)

    ok = process_kb_job(current.id)
    assert ok is False

    test_db_session.expire_all()
    refreshed = test_db_session.get(KBJob, current.id)
    assert refreshed is not None
    assert refreshed.status == "error"
    assert (refreshed.error_message or "").startswith("worker_exception:")

