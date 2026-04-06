from datetime import datetime

import pytest
from sqlalchemy.orm import sessionmaker

from apps.backend.database import Base, get_test_engine
from apps.backend.models.account import Account, AccountMembership, AccountUserGroup, AccountUserGroupMember, AppUser
from apps.backend.models.kb import KBFile, KBFileAccess, KBFolder, KBFolderAccess
from apps.backend.models.portal import Portal
from apps.backend.services.kb_acl import (
    default_kb_access_for_role,
    kb_acl_principals_for_membership,
    normalize_kb_principal,
    resolve_kb_acl_access,
)


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


def test_kb_acl_foundation_supports_folder_tree_and_file_binding(test_db_session):
    account = Account(name="ACL Account")
    portal = Portal(domain="acl.bitrix24.ru", status="active")
    test_db_session.add_all([account, portal])
    test_db_session.flush()

    root = KBFolder(account_id=account.id, portal_id=portal.id, name="Dept")
    test_db_session.add(root)
    test_db_session.flush()

    child = KBFolder(account_id=account.id, portal_id=portal.id, parent_id=root.id, name="Policies")
    test_db_session.add(child)
    test_db_session.flush()

    file_row = KBFile(
        account_id=account.id,
        portal_id=portal.id,
        folder_id=child.id,
        filename="policy.pdf",
        mime_type="application/pdf",
        size_bytes=1,
        storage_path="/tmp/policy.pdf",
        status="ready",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    test_db_session.add(file_row)
    test_db_session.commit()

    persisted = test_db_session.get(KBFile, file_row.id)
    assert persisted is not None
    assert persisted.folder_id == child.id


def test_kb_acl_foundation_supports_folder_and_file_acl_rows(test_db_session):
    account = Account(name="ACL Account")
    portal = Portal(domain="acl2.bitrix24.ru", status="active")
    test_db_session.add_all([account, portal])
    test_db_session.flush()

    folder = KBFolder(account_id=account.id, portal_id=portal.id, name="Clients")
    file_row = KBFile(
        account_id=account.id,
        portal_id=portal.id,
        filename="client-doc.pdf",
        mime_type="application/pdf",
        size_bytes=1,
        storage_path="/tmp/client-doc.pdf",
        status="ready",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    test_db_session.add_all([folder, file_row])
    test_db_session.flush()

    test_db_session.add(
        KBFolderAccess(folder_id=folder.id, principal_type="role", principal_id="client", access_level="read")
    )
    test_db_session.add(
        KBFileAccess(file_id=file_row.id, principal_type="membership", principal_id="42", access_level="read")
    )
    test_db_session.commit()

    assert test_db_session.query(KBFolderAccess).count() == 1
    assert test_db_session.query(KBFileAccess).count() == 1


def test_kb_acl_foundation_role_defaults_and_principal_normalization():
    assert default_kb_access_for_role("owner") == "manage"
    assert default_kb_access_for_role("admin") == "edit"
    assert default_kb_access_for_role("member") == "read"
    assert default_kb_access_for_role("client") == "none"
    assert normalize_kb_principal("role", "client") == ("role", "client")
    principals = kb_acl_principals_for_membership(42, "member", "client")
    assert ("membership", "42") in principals
    assert ("role", "member") in principals
    assert ("audience", "client") in principals
    access = resolve_kb_acl_access(
        [
            ("role", "member", "read"),
            ("membership", "42", "edit"),
            ("audience", "client", "none"),
        ],
        principals,
    )
    assert access == "edit"
    restricted = resolve_kb_acl_access(
        [("membership", "99", "read")],
        principals,
        inherited_access="read",
    )
    assert restricted == "none"


def test_kb_acl_foundation_supports_group_principals(test_db_session):
    account = Account(name="ACL Account")
    portal = Portal(domain="acl3.bitrix24.ru", status="active")
    user = AppUser(display_name="Member", status="active")
    test_db_session.add_all([account, portal, user])
    test_db_session.flush()

    membership = AccountMembership(account_id=account.id, user_id=user.id, role="member", status="active")
    test_db_session.add(membership)
    test_db_session.flush()

    group = AccountUserGroup(account_id=account.id, name="Sales")
    test_db_session.add(group)
    test_db_session.flush()
    test_db_session.add(AccountUserGroupMember(group_id=group.id, membership_id=membership.id))
    test_db_session.flush()

    folder = KBFolder(account_id=account.id, portal_id=portal.id, name="Sales")
    test_db_session.add(folder)
    test_db_session.flush()
    test_db_session.add(
        KBFolderAccess(folder_id=folder.id, principal_type="group", principal_id=str(group.id), access_level="read")
    )
    test_db_session.commit()

    principals = kb_acl_principals_for_membership(membership.id, "member", "staff", [group.id])
    assert ("group", str(group.id)) in principals
    access = resolve_kb_acl_access(
        [("group", str(group.id), "read")],
        principals,
        inherited_access="none",
    )
    assert access == "read"
