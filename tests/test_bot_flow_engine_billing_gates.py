from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from apps.backend.database import Base, get_test_engine
from apps.backend.models.account import Account
from apps.backend.models.billing import AccountPlanOverride, AccountSubscription, BillingPlan
from apps.backend.models.portal import Portal
from apps.backend.models.portal_bot_flow import PortalBotFlow
from apps.backend.services.billing import ensure_base_plans
from apps.backend.services.bot_flow_engine import execute_client_flow


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
def test_execute_client_flow_returns_lock_message_when_client_bot_disabled(test_db_session):
    account = Account(name="Locked flow", status="active")
    test_db_session.add(account)
    test_db_session.commit()
    test_db_session.refresh(account)
    ensure_base_plans(test_db_session)
    business_plan = test_db_session.query(BillingPlan).filter(BillingPlan.code == "business").one()
    test_db_session.add(
        AccountSubscription(account_id=account.id, plan_id=business_plan.id, status="active", started_at=datetime.utcnow())
    )
    test_db_session.add(
        AccountPlanOverride(
            account_id=account.id,
            features_json={"allow_client_bot": False},
            valid_from=datetime.utcnow() - timedelta(days=1),
            valid_to=datetime.utcnow() + timedelta(days=1),
            reason="test",
            created_by="test",
        )
    )
    portal = Portal(domain="flow-disabled.bitrix24.ru", status="active", admin_user_id=1, account_id=account.id)
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)
    test_db_session.add(
        PortalBotFlow(
            portal_id=portal.id,
            kind="client",
            published_json={
                "version": 1,
                "settings": {},
                "nodes": [{"id": "start", "type": "start"}, {"id": "msg", "type": "message", "config": {"text": "hi"}}],
                "edges": [{"from": "start", "to": "msg"}],
            },
        )
    )
    test_db_session.commit()

    text = execute_client_flow(test_db_session, portal.id, 0, "hello")
    assert "недоступна" in text.lower()


@pytest.mark.timeout(10)
def test_execute_client_flow_skips_webhook_when_webhooks_disabled(test_db_session, monkeypatch):
    calls: list[dict] = []

    def fake_post(url, json=None, timeout=None):
        calls.append({"url": url, "json": json, "timeout": timeout})
        class Resp:
            status_code = 200
        return Resp()

    monkeypatch.setattr("apps.backend.services.bot_flow_engine.httpx.post", fake_post)

    account = Account(name="No webhooks", status="active")
    test_db_session.add(account)
    test_db_session.commit()
    test_db_session.refresh(account)
    ensure_base_plans(test_db_session)
    start_plan = test_db_session.query(BillingPlan).filter(BillingPlan.code == "start").one()
    test_db_session.add(
        AccountSubscription(account_id=account.id, plan_id=start_plan.id, status="active", started_at=datetime.utcnow())
    )
    portal = Portal(domain="flow-no-webhooks.bitrix24.ru", status="active", admin_user_id=1, account_id=account.id)
    test_db_session.add(portal)
    test_db_session.commit()
    test_db_session.refresh(portal)
    test_db_session.add(
        PortalBotFlow(
            portal_id=portal.id,
            kind="client",
            published_json={
                "version": 1,
                "settings": {},
                "nodes": [
                    {"id": "start", "type": "start"},
                    {"id": "wh", "type": "webhook", "config": {"url": "https://example.test/hook", "payload": {"a": 1}}},
                    {"id": "msg", "type": "message", "config": {"text": "done"}},
                ],
                "edges": [{"from": "start", "to": "wh"}, {"from": "wh", "to": "msg"}],
            },
        )
    )
    test_db_session.commit()

    text = execute_client_flow(test_db_session, portal.id, 0, "hello")
    assert text == "done"
    assert calls == []
