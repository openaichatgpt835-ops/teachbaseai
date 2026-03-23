from datetime import datetime, timedelta

from sqlalchemy.orm import sessionmaker

from apps.backend.database import Base, get_test_engine
from apps.backend.models.account import Account, AppUser, AppUserWebCredential
from apps.backend.models.portal import Portal
from apps.backend.models.web_user import WebUser
from apps.backend.routers.bitrix import _resolve_linked_web_user


def _make_db():
    engine = get_test_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_resolve_linked_web_user_prefers_owner_email_for_portal():
    db = _make_db()
    try:
        portal = Portal(domain="foo.bitrix24.ru", status="active", admin_user_id=1, metadata_json='{"owner_email":"owner@example.com"}')
        db.add(portal)
        db.commit()
        db.refresh(portal)

        owner = WebUser(
            email="owner@example.com",
            password_hash="x",
            portal_id=portal.id,
            email_verified_at=datetime.utcnow(),
        )
        member = WebUser(
            email="member@example.com",
            password_hash="x",
            portal_id=portal.id,
            email_verified_at=datetime.utcnow(),
        )
        db.add_all([owner, member])
        db.commit()

        picked = _resolve_linked_web_user(db, portal)
        assert picked is not None
        assert picked.email == "owner@example.com"
    finally:
        db.close()


def test_resolve_linked_web_user_handles_multiple_users_same_portal_without_error():
    db = _make_db()
    try:
        portal = Portal(domain="bar.bitrix24.ru", status="active", admin_user_id=1)
        db.add(portal)
        db.commit()
        db.refresh(portal)

        older = WebUser(
            email="older@example.com",
            password_hash="x",
            portal_id=portal.id,
            created_at=datetime.utcnow() - timedelta(days=2),
            email_verified_at=None,
        )
        newer_verified = WebUser(
            email="verified@example.com",
            password_hash="x",
            portal_id=portal.id,
            created_at=datetime.utcnow() - timedelta(days=1),
            email_verified_at=datetime.utcnow(),
        )
        db.add_all([older, newer_verified])
        db.commit()

        picked = _resolve_linked_web_user(db, portal)
        assert picked is not None
        assert picked.email == "verified@example.com"
    finally:
        db.close()


def test_resolve_linked_web_user_uses_account_owner_when_metadata_missing():
    db = _make_db()
    try:
        app_user = AppUser(display_name="Owner", status="active")
        db.add(app_user)
        db.flush()
        cred = AppUserWebCredential(
            user_id=app_user.id,
            login="owner@example.com",
            email="owner@example.com",
            password_hash="x",
        )
        account = Account(account_no=100001, name="Test", status="active", owner_user_id=app_user.id)
        db.add_all([cred, account])
        db.flush()
        portal = Portal(domain="baz.bitrix24.ru", status="active", admin_user_id=1, account_id=account.id)
        db.add(portal)
        db.flush()
        linked = WebUser(
            email="owner@example.com",
            password_hash="x",
            portal_id=portal.id,
            email_verified_at=datetime.utcnow(),
        )
        other = WebUser(
            email="other@example.com",
            password_hash="x",
            portal_id=portal.id,
            email_verified_at=datetime.utcnow(),
        )
        db.add_all([linked, other])
        db.commit()

        picked = _resolve_linked_web_user(db, portal)
        assert picked is not None
        assert picked.email == "owner@example.com"
    finally:
        db.close()
