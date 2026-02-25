from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from apps.backend.database import Base, get_test_engine
from apps.backend.models.account import AccountMembership, AccountPermission, AppUserWebCredential
from apps.backend.models.portal import Portal
from apps.backend.models.web_user import WebUser
from apps.backend.services.rbac_service import ensure_rbac_for_web_user


@pytest.fixture
def db():
    engine = get_test_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def test_register_flow_user_gets_owner_permissions(db):
    portal = Portal(domain="web:test", status="active", install_type="web")
    db.add(portal)
    db.flush()
    wu = WebUser(
        email="owner1@example.com",
        password_hash="hash",
        portal_id=portal.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(wu)
    db.flush()

    account_id, app_user_id = ensure_rbac_for_web_user(db, wu, force_owner=True, account_name="Acme")
    db.commit()

    assert account_id is not None
    assert app_user_id is not None
    portal = db.get(Portal, portal.id)
    assert int(portal.account_id or 0) == int(account_id)

    cred = db.execute(
        select(AppUserWebCredential).where(AppUserWebCredential.user_id == app_user_id)
    ).scalar_one()
    assert cred.email == "owner1@example.com"

    membership = db.execute(
        select(AccountMembership).where(
            AccountMembership.account_id == account_id,
            AccountMembership.user_id == app_user_id,
        )
    ).scalar_one()
    assert membership.role == "owner"
    assert membership.status == "active"

    perm = db.execute(
        select(AccountPermission).where(AccountPermission.membership_id == membership.id)
    ).scalar_one()
    assert perm.kb_access == "write"
    assert perm.can_invite_users is True
    assert perm.can_manage_settings is True
    assert perm.can_view_finance is True


def test_existing_owner_email_gets_owner_role(db):
    portal = Portal(
        domain="b24-owner.bitrix24.ru",
        status="active",
        install_type="local",
        metadata_json='{"owner_email":"owner2@example.com","company":"T2"}',
    )
    db.add(portal)
    db.flush()
    wu = WebUser(
        email="owner2@example.com",
        password_hash="hash",
        portal_id=portal.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(wu)
    db.flush()

    account_id, app_user_id = ensure_rbac_for_web_user(db, wu)
    db.commit()

    membership = db.execute(
        select(AccountMembership).where(
            AccountMembership.account_id == account_id,
            AccountMembership.user_id == app_user_id,
        )
    ).scalar_one()
    assert membership.role == "owner"
    perm = db.execute(
        select(AccountPermission).where(AccountPermission.membership_id == membership.id)
    ).scalar_one()
    assert perm.kb_access == "write"
