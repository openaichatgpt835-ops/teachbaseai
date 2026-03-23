import importlib.util
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

if importlib.util.find_spec("jose") is None:
    pytest.skip("python-jose is required for API app import in this environment", allow_module_level=True)

from apps.backend.database import Base, get_test_engine
from apps.backend.deps import get_db
from apps.backend.main import app
from apps.backend.models.kb import KBFile
from apps.backend.models.portal import Portal
from apps.backend.models.portal_kb_setting import PortalKBSetting
from apps.backend.routers import bitrix as bitrix_router

client = TestClient(app)


def test_transcript_mode_raw_vs_merged(tmp_path):
    engine = get_test_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    def _get_db():
        try:
            yield db
        finally:
            pass

    portal = Portal(domain="transcript-mode.bitrix24.ru", status="active", admin_user_id=1)
    db.add(portal)
    db.flush()

    db.add(PortalKBSetting(portal_id=portal.id, media_transcription_enabled=True))

    media_path = tmp_path / "sample.mp3"
    media_path.write_bytes(b"x")

    rec = KBFile(
        portal_id=portal.id,
        filename="sample.mp3",
        mime_type="audio/mpeg",
        size_bytes=1,
        storage_path=str(media_path),
        status="ready",
        transcript_status="ready",
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    transcript_path = tmp_path / "sample.mp3.transcript.jsonl"
    rows = [
        {"speaker": "Спикер A", "text": "Привет", "start_ms": 1000, "end_ms": 1500},
        {"speaker": "Спикер A", "text": "как дела", "start_ms": 1600, "end_ms": 2100},
        {"speaker": "Спикер B", "text": "нормально", "start_ms": 2200, "end_ms": 2600},
    ]
    with transcript_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[bitrix_router.require_portal_access] = lambda: portal.id
    try:
        r_raw = client.get(f"/v1/bitrix/portals/{portal.id}/kb/files/{rec.id}/transcript?mode=raw")
        r_merged = client.get(f"/v1/bitrix/portals/{portal.id}/kb/files/{rec.id}/transcript?mode=merged")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(bitrix_router.require_portal_access, None)
        db.close()

    assert r_raw.status_code == 200
    assert r_merged.status_code == 200

    raw = r_raw.json()
    merged = r_merged.json()

    assert raw.get("mode") == "raw"
    assert merged.get("mode") == "merged"
    assert int(raw.get("raw_count") or 0) == 3
    assert int(raw.get("merged_count") or 0) == 2
    assert len(raw.get("items") or []) == 3
    assert len(merged.get("items") or []) == 2
