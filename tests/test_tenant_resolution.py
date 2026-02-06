"""Tenant resolution for inbound events."""
import pytest
from sqlalchemy.orm import sessionmaker

from apps.backend.database import get_test_engine, Base
from apps.backend.models.portal import Portal
from apps.backend.services.bitrix_inbound_log import build_inbound_event_record


def _db():
    engine = get_test_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@pytest.mark.timeout(10)
def test_resolve_by_member_id_updates_domain():
    db = _db()
    p = Portal(domain="old.example", member_id="m1", status="active")
    db.add(p)
    db.commit()

    payload = {
        "event": "ONIMBOTMESSAGEADD",
        "auth": {"member_id": "m1", "domain": "new.example"},
        "data": {"DIALOG_ID": "user1", "USER_ID": 1},
    }
    import json as _json
    rec = build_inbound_event_record(
        db,
        trace_id="t1",
        method="POST",
        path="/v1/bitrix/events",
        query_string=None,
        content_type="application/json",
        request_headers={},
        body_bytes=_json.dumps(payload).encode(),
        remote_ip=None,
        query_domain=None,
        settings={"max_body_kb": 128},
    )
    db.refresh(p)
    assert rec.portal_id == p.id
    assert p.domain == "new.example"


@pytest.mark.timeout(10)
def test_resolve_by_domain_when_member_id_missing():
    db = _db()
    p = Portal(domain="b24.example", status="active")
    db.add(p)
    db.commit()

    payload = {"event": "ONIMBOTMESSAGEADD", "data": {"DIALOG_ID": "user1"}}
    import json as _json
    rec = build_inbound_event_record(
        db,
        trace_id="t2",
        method="POST",
        path="/v1/bitrix/events",
        query_string=None,
        content_type="application/json",
        request_headers={},
        body_bytes=_json.dumps(payload).encode(),
        remote_ip=None,
        query_domain="b24.example",
        settings={"max_body_kb": 128},
    )
    assert rec.portal_id == p.id
