"""Inbound event parsing for dialog_id/user_id."""
import pytest
from sqlalchemy.orm import sessionmaker

from apps.backend.database import get_test_engine, Base
from apps.backend.services.bitrix_inbound_log import build_inbound_event_record


def _db():
    engine = get_test_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@pytest.mark.timeout(10)
def test_onimbotmessageadd_extracts_dialog_and_user():
    db = _db()
    payload = {
        "event": "ONIMBOTMESSAGEADD",
        "data": {
            "DIALOG_ID": "user42",
            "USER_ID": 42,
            "MESSAGE": "ping",
        },
        "auth": {"member_id": "m42", "domain": "b24.example"},
    }
    rec = build_inbound_event_record(
        db,
        trace_id="t3",
        method="POST",
        path="/v1/bitrix/events",
        query_string=None,
        content_type="application/json",
        request_headers={},
        body_bytes=str(payload).encode(),
        remote_ip=None,
        query_domain=None,
        settings={"max_body_kb": 128},
    )
    assert rec.dialog_id == "user42"
    assert rec.user_id == "42"
    assert rec.event_name == "ONIMBOTMESSAGEADD"
