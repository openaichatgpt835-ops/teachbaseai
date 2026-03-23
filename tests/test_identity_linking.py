from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from apps.backend.database import Base, get_test_engine
from apps.backend.models.account import Account, AccountIntegration, AccountMembership, AppUser, AppUserIdentity, AppUserWebCredential
from apps.backend.services.identity_linking import link_or_create_app_user


@pytest.fixture
def db():
    engine = get_test_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_account_with_integration(db, *, account_no: int, name: str, external_key: str):
    account = Account(account_no=account_no, name=name, slug=name.lower().replace(" ", "-"), status="active")
    db.add(account)
    db.flush()
    integ = AccountIntegration(
        account_id=account.id,
        provider="bitrix",
        status="active",
        external_key=external_key,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(integ)
    db.flush()
    db.commit()
    return account, integ


def test_identity_linking_returns_existing_identity(db):
    account, integ = _seed_account_with_integration(db, account_no=1001, name="Acme KB", external_key="a.bitrix24.ru")
    user = AppUser(display_name="Alex", status="active")
    db.add(user)
    db.flush()
    db.add(
        AppUserIdentity(
            user_id=user.id,
            provider="bitrix",
            integration_id=integ.id,
            external_id="42",
            display_value="Алексей",
            created_at=datetime.utcnow(),
        )
    )
    db.commit()

    result = link_or_create_app_user(
        db,
        provider="bitrix",
        integration_id=integ.id,
        external_id="42",
        display_value="Алексей Лагутин",
    )

    assert result.status == "existing_identity"
    assert result.user_id == user.id
    ident = db.execute(select(AppUserIdentity).where(AppUserIdentity.id == result.identity_id)).scalar_one()
    assert ident.display_value == "Алексей Лагутин"
    assert result.account_id == account.id


def test_identity_linking_links_by_email_across_accounts(db):
    account_a, integ_a = _seed_account_with_integration(db, account_no=1002, name="Acme A", external_key="a.bitrix24.ru")
    account_b, integ_b = _seed_account_with_integration(db, account_no=1003, name="Acme B", external_key="b.bitrix24.ru")
    user = AppUser(display_name="Alex", status="active")
    db.add(user)
    db.flush()
    db.add(
        AppUserWebCredential(
            user_id=user.id,
            login="alex@example.com",
            email="alex@example.com",
            password_hash="hash",
            email_verified_at=datetime.utcnow(),
        )
    )
    db.add(AccountMembership(account_id=account_a.id, user_id=user.id, role="member", status="active"))
    db.commit()

    result_same = link_or_create_app_user(
        db,
        provider="bitrix",
        integration_id=integ_a.id,
        external_id="42",
        display_value="Алексей",
        email="alex@example.com",
    )
    assert result_same.status == "linked_by_email"
    assert result_same.user_id == user.id

    result_other = link_or_create_app_user(
        db,
        provider="bitrix",
        integration_id=integ_b.id,
        external_id="77",
        display_value="Алексей",
        email="alex@example.com",
    )
    assert result_other.status == "linked_by_email"
    assert result_other.user_id == user.id
    assert result_other.matched_user_id == user.id
    assert result_other.account_id == account_b.id


def test_identity_linking_creates_user_when_no_safe_match(db):
    _, integ = _seed_account_with_integration(db, account_no=1004, name="Acme C", external_key="c.bitrix24.ru")
    result = link_or_create_app_user(
        db,
        provider="bitrix",
        integration_id=integ.id,
        external_id="13",
        display_value="Новый Пользователь",
        email="new@example.com",
    )
    assert result.status == "created_user"
    assert result.user_id is not None
    ident = db.execute(select(AppUserIdentity).where(AppUserIdentity.id == result.identity_id)).scalar_one()
    assert ident.user_id == result.user_id


def test_identity_linking_expected_user_wins(db):
    _, integ = _seed_account_with_integration(db, account_no=1005, name="Acme D", external_key="d.bitrix24.ru")
    user = AppUser(display_name="Manual Link", status="active")
    db.add(user)
    db.commit()

    result = link_or_create_app_user(
        db,
        provider="bitrix",
        integration_id=integ.id,
        external_id="99",
        expected_app_user_id=user.id,
        display_value="Linked User",
    )
    assert result.status == "linked_expected_user"
    assert result.user_id == user.id
