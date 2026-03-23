from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from apps.backend.database import Base, get_test_engine
from apps.backend.models.account import Account, AppSession, AccountMembership, AppUserWebCredential
from apps.backend.models.portal import Portal
from apps.backend.models.web_user import WebSession, WebUser
from apps.backend.scripts.backfill_account_auth_v2 import run as run_backfill
from apps.backend.scripts.validate_account_auth_v2 import run as run_validate
from apps.backend.services.account_workspace import build_unique_account_slug


@pytest.fixture
def session_factory():
    engine = get_test_engine()
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_build_unique_account_slug_adds_suffix(session_factory):
    db = session_factory()
    try:
        db.add_all(
            [
                Account(account_no=100001, name="Necrogame / База знаний", slug="necrogame", status="active"),
                Account(account_no=100002, name="Necrogame / AI ROP", slug="necrogame-2", status="active"),
            ]
        )
        db.commit()

        slug = build_unique_account_slug(db, "Necrogame", fallback="workspace-100003")
        assert slug == "necrogame-3"
    finally:
        db.close()


def test_backfill_account_auth_v2_populates_slug_membership_and_app_session(session_factory):
    seed = session_factory()
    try:
        account = Account(account_no=100100, name="Acme / KB", slug=None, status="active")
        seed.add(account)
        seed.flush()

        portal = Portal(domain="web:acme", status="active", install_type="web", account_id=account.id)
        seed.add(portal)
        seed.flush()

        web_user = WebUser(
            email="owner@example.com",
            password_hash="hash",
            portal_id=portal.id,
            email_verified_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        seed.add(web_user)
        seed.flush()

        seed.add(
            WebSession(
                user_id=web_user.id,
                token="tok-owner",
                app_user_id=None,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=1),
            )
        )
        seed.commit()
    finally:
        seed.close()

    stats = run_backfill(session_factory(), commit=True)
    assert stats.failed == 0
    assert stats.accounts_slugged == 1
    assert stats.sessions_mirrored == 1

    check = session_factory()
    try:
        account = check.query(Account).filter(Account.account_no == 100100).one()
        assert account.slug == "acme-kb"
        assert account.owner_user_id is not None

        membership = (
            check.query(AccountMembership)
            .filter(AccountMembership.account_id == account.id, AccountMembership.role == "owner")
            .one()
        )
        cred = (
            check.query(AppUserWebCredential)
            .filter(AppUserWebCredential.user_id == membership.user_id)
            .one()
        )
        assert cred.email == "owner@example.com"

        app_session = check.query(AppSession).filter(AppSession.token == "tok-owner").one()
        assert app_session.active_account_id == account.id

        web_session = check.query(WebSession).filter(WebSession.token == "tok-owner").one()
        assert web_session.app_user_id == membership.user_id
    finally:
        check.close()


def test_validate_account_auth_v2_reports_missing_invariants(session_factory):
    db = session_factory()
    try:
        account = Account(account_no=100200, name="Broken", slug=None, status="active", owner_user_id=None)
        db.add(account)
        db.flush()
        db.add(Portal(domain="web:broken", status="active", install_type="web", account_id=None))
        db.commit()
    finally:
        db.close()

    result = run_validate(session_factory())
    assert result.ok is False
    assert result.accounts_without_slug
    assert result.accounts_without_owner
    assert result.portals_without_account
