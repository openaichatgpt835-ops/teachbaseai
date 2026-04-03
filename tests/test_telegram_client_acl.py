from datetime import datetime

from sqlalchemy.orm import sessionmaker

from apps.backend.database import Base, get_test_engine
from apps.backend.models.account import (
    Account,
    AccountMembership,
    AccountPermission,
    AccountUserGroup,
    AccountUserGroupMember,
    AppUser,
    AppUserIdentity,
)
from apps.backend.models.kb import KBFile, KBFileAccess, KBFolder, KBFolderAccess
from apps.backend.models.portal import Portal
from apps.backend.models.dialog import Message
from apps.backend.services import telegram_events


def test_telegram_client_bot_respects_client_group_acl():
    engine = get_test_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        account = Account(account_no=555001, name="Client Bot ACL", status="active")
        db.add(account)
        db.flush()

        portal = Portal(domain="client-bot.bitrix24.ru", status="active", account_id=account.id)
        db.add(portal)
        db.flush()

        user = AppUser(display_name="Client", status="active")
        db.add(user)
        db.flush()

        membership = AccountMembership(account_id=account.id, user_id=user.id, role="client", status="active")
        db.add(membership)
        db.flush()
        db.add(
            AccountPermission(
                membership_id=membership.id,
                kb_access="none",
                can_invite_users=False,
                can_manage_settings=False,
                can_view_finance=False,
            )
        )
        db.flush()

        group = AccountUserGroup(account_id=account.id, name="Acme Clients", kind="client")
        db.add(group)
        db.flush()
        db.add(AccountUserGroupMember(group_id=group.id, membership_id=membership.id))
        db.add(
            AppUserIdentity(
                user_id=user.id,
                provider="telegram",
                integration_id=None,
                external_id="client_acme",
                display_value="@client_acme",
                created_at=datetime.utcnow(),
            )
        )
        file_rec = KBFile(
            account_id=account.id,
            portal_id=portal.id,
            filename="client-only.txt",
            audience="client",
            mime_type="text/plain",
            size_bytes=10,
            storage_path="/tmp/client-only.txt",
            status="ready",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(file_rec)
        db.flush()
        db.add(KBFileAccess(file_id=file_rec.id, principal_type="group", principal_id=str(group.id), access_level="read"))
        db.commit()

        captured: dict[str, object] = {}
        original_execute_client_flow = telegram_events.execute_client_flow

        def _fake_execute_client_flow(db, portal_id, dialog_id, user_text, *, file_ids_filter=None):
            captured["file_ids_filter"] = file_ids_filter
            return "ok"

        telegram_events.execute_client_flow = _fake_execute_client_flow
        try:
            update = {
                "update_id": 101,
                "message": {
                    "message_id": 201,
                    "chat": {"id": 301, "type": "private"},
                    "from": {"id": 401, "username": "client_acme"},
                    "text": "policy",
                },
            }
            allowed = telegram_events.process_telegram_update(db, portal.id, "client", update)
            assert allowed["status"] == "ok"
            assert captured["file_ids_filter"] == [file_rec.id]
            tx_allowed = db.query(Message).filter(Message.direction == "tx").order_by(Message.id.desc()).first()
            assert tx_allowed is not None
            assert tx_allowed.body == "ok"

            db.query(AccountUserGroupMember).filter(
                AccountUserGroupMember.group_id == group.id,
                AccountUserGroupMember.membership_id == membership.id,
            ).delete()
            db.commit()
            captured.clear()

            denied = telegram_events.process_telegram_update(db, portal.id, "client", update)
            assert denied["status"] == "ok"
            assert "file_ids_filter" not in captured
            tx_denied = db.query(Message).filter(Message.direction == "tx").order_by(Message.id.desc()).first()
            assert tx_denied is not None
            assert tx_denied.body == telegram_events.MSG_NO_CLIENT_MATERIALS
        finally:
            telegram_events.execute_client_flow = original_execute_client_flow
    finally:
        db.close()


def test_telegram_client_bot_respects_folder_client_group_acl_inheritance():
    engine = get_test_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        account = Account(account_no=555002, name="Client Bot Folder ACL", status="active")
        db.add(account)
        db.flush()

        portal = Portal(domain="client-folder.bitrix24.ru", status="active", account_id=account.id)
        db.add(portal)
        db.flush()

        user = AppUser(display_name="Client Folder User", status="active")
        db.add(user)
        db.flush()

        membership = AccountMembership(account_id=account.id, user_id=user.id, role="client", status="active")
        db.add(membership)
        db.flush()
        db.add(
            AccountPermission(
                membership_id=membership.id,
                kb_access="none",
                can_invite_users=False,
                can_manage_settings=False,
                can_view_finance=False,
            )
        )
        db.flush()

        group = AccountUserGroup(account_id=account.id, name="Folder Clients", kind="client")
        db.add(group)
        db.flush()
        db.add(AccountUserGroupMember(group_id=group.id, membership_id=membership.id))
        db.add(
            AppUserIdentity(
                user_id=user.id,
                provider="telegram",
                integration_id=None,
                external_id="folder_client",
                display_value="@folder_client",
                created_at=datetime.utcnow(),
            )
        )

        folder = KBFolder(
            account_id=account.id,
            portal_id=portal.id,
            name="Client Folder",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(folder)
        db.flush()
        db.add(
            KBFolderAccess(folder_id=folder.id, principal_type="group", principal_id=str(group.id), access_level="read")
        )

        file_rec = KBFile(
            account_id=account.id,
            portal_id=portal.id,
            folder_id=folder.id,
            filename="folder-client-only.txt",
            audience="client",
            mime_type="text/plain",
            size_bytes=10,
            storage_path="/tmp/folder-client-only.txt",
            status="ready",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(file_rec)
        db.commit()

        captured: dict[str, object] = {}
        original_execute_client_flow = telegram_events.execute_client_flow

        def _fake_execute_client_flow(db, portal_id, dialog_id, user_text, *, file_ids_filter=None):
            captured["file_ids_filter"] = file_ids_filter
            return "ok-folder"

        telegram_events.execute_client_flow = _fake_execute_client_flow
        try:
            update = {
                "update_id": 102,
                "message": {
                    "message_id": 202,
                    "chat": {"id": 302, "type": "private"},
                    "from": {"id": 402, "username": "folder_client"},
                    "text": "folder policy",
                },
            }
            allowed = telegram_events.process_telegram_update(db, portal.id, "client", update)
            assert allowed["status"] == "ok"
            assert captured["file_ids_filter"] == [file_rec.id]
            tx_allowed = db.query(Message).filter(Message.direction == "tx").order_by(Message.id.desc()).first()
            assert tx_allowed is not None
            assert tx_allowed.body == "ok-folder"

            db.query(KBFolderAccess).filter(KBFolderAccess.folder_id == folder.id).delete()
            db.commit()
            captured.clear()

            denied = telegram_events.process_telegram_update(db, portal.id, "client", update)
            assert denied["status"] == "ok"
            assert "file_ids_filter" not in captured
            tx_denied = db.query(Message).filter(Message.direction == "tx").order_by(Message.id.desc()).first()
            assert tx_denied is not None
            assert tx_denied.body == telegram_events.MSG_NO_CLIENT_MATERIALS
        finally:
            telegram_events.execute_client_flow = original_execute_client_flow
    finally:
        db.close()
