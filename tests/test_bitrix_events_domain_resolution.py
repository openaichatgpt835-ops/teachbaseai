import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from apps.backend.database import Base, get_test_engine
from apps.backend.models.dialog import Dialog, Message
from apps.backend.models.event import Event
from apps.backend.models.outbox import Outbox
from apps.backend.models.portal import Portal
from apps.backend.services.bitrix_events import process_imbot_message


def _db():
    engine = get_test_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@pytest.mark.timeout(10)
def test_process_imbot_message_resolves_exact_domain():
    db = _db()
    p_foo = Portal(domain="foo.bitrix24.ru", status="active")
    p_other = Portal(domain="my-foo-team.bitrix24.ru", status="active")
    db.add(p_foo)
    db.add(p_other)
    db.commit()
    db.refresh(p_foo)
    db.refresh(p_other)

    data = {
        "PARAMS": {
            "DIALOG_ID": "user123",
            "MESSAGE_ID": "msg-foo-1",
            "MESSAGE": "ping",
        }
    }
    auth = {"domain": "foo.bitrix24.ru"}

    result = process_imbot_message(db, data, auth)
    assert result.get("status") == "ok"

    ev = db.execute(select(Event).where(Event.provider_event_id == "msg-foo-1")).scalar_one()
    assert ev.portal_id == p_foo.id
    assert ev.portal_id != p_other.id

    dlg = db.execute(
        select(Dialog).where(Dialog.portal_id == p_foo.id, Dialog.provider_dialog_id == "123")
    ).scalar_one()
    assert dlg.portal_id == p_foo.id

    msgs = db.execute(select(Message).where(Message.dialog_id == dlg.id)).scalars().all()
    assert len(msgs) == 2
    assert all(m.dialog_id == dlg.id for m in msgs)

    outbox = db.execute(select(Outbox).where(Outbox.portal_id == p_foo.id)).scalar_one()
    assert outbox.portal_id == p_foo.id

