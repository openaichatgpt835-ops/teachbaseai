"""KB watchdog recovery tests."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from apps.backend.database import Base, get_test_engine
from apps.backend.models.portal import Portal
from apps.backend.models.kb import KBFile, KBJob
from apps.backend.services import kb_job_watchdog


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
def test_recover_stuck_kb_jobs_requeues_file(test_db_session, monkeypatch):
    portal = Portal(domain="watchdog.bitrix24.ru", status="active")
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)

    file_rec = KBFile(
        portal_id=portal.id,
        filename="stuck.mp3",
        audience="staff",
        mime_type="audio/mpeg",
        size_bytes=123,
        storage_path="/tmp/stuck.mp3",
        status="processing",
    )
    test_db_session.add(file_rec)
    test_db_session.commit()
    test_db_session.refresh(file_rec)

    old = datetime.utcnow() - timedelta(minutes=30)
    file_rec.updated_at = old
    stuck_job = KBJob(
        portal_id=portal.id,
        job_type="ingest",
        status="processing",
        payload_json={"file_id": file_rec.id},
        updated_at=old,
        created_at=old,
    )
    test_db_session.add(stuck_job)
    test_db_session.commit()

    SessionLocal = sessionmaker(bind=test_db_session.bind)
    monkeypatch.setattr(kb_job_watchdog, "get_session_factory", lambda: SessionLocal)

    result = kb_job_watchdog.recover_stuck_kb_jobs_once(stale_seconds=60, batch_limit=50)
    assert result["stuck_jobs_failed"] >= 1
    assert result["jobs_created"] >= 1

    test_db_session.expire_all()
    jobs = (
        test_db_session.query(KBJob)
        .filter(KBJob.portal_id == portal.id)
        .order_by(KBJob.id.asc())
        .all()
    )
    assert jobs[0].status == "failed"
    assert jobs[0].error_message == "stuck_processing_timeout"
    assert any(j.status == "queued" and (j.payload_json or {}).get("file_id") == file_rec.id for j in jobs[1:])

    file_fresh = test_db_session.get(KBFile, file_rec.id)
    assert file_fresh is not None
    assert file_fresh.status == "queued"


@pytest.mark.timeout(10)
def test_recover_stale_uploaded_file_without_job(test_db_session, monkeypatch):
    portal = Portal(domain="watchdog-uploaded.bitrix24.ru", status="active")
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)

    old = datetime.utcnow() - timedelta(minutes=30)
    file_rec = KBFile(
        portal_id=portal.id,
        filename="uploaded_only.ogg",
        audience="staff",
        mime_type="audio/ogg",
        size_bytes=456,
        storage_path="/tmp/uploaded_only.ogg",
        status="uploaded",
        updated_at=old,
        created_at=old,
    )
    test_db_session.add(file_rec)
    test_db_session.commit()
    test_db_session.refresh(file_rec)

    SessionLocal = sessionmaker(bind=test_db_session.bind)
    monkeypatch.setattr(kb_job_watchdog, "get_session_factory", lambda: SessionLocal)

    result = kb_job_watchdog.recover_stuck_kb_jobs_once(stale_seconds=60, batch_limit=50)
    assert result["jobs_created"] >= 1

    test_db_session.expire_all()
    file_fresh = test_db_session.get(KBFile, file_rec.id)
    assert file_fresh is not None
    assert file_fresh.status == "queued"
    queued_jobs = (
        test_db_session.query(KBJob)
        .filter(KBJob.portal_id == portal.id, KBJob.status == "queued")
        .all()
    )
    assert any((j.payload_json or {}).get("file_id") == file_rec.id for j in queued_jobs)
