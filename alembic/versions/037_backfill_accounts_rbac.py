"""backfill accounts, app users and memberships from legacy tables

Revision ID: 037_backfill_accounts_rbac
Revises: 036_invites_and_audit
Create Date: 2026-02-22
"""

from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "037_backfill_accounts_rbac"
down_revision = "036_invites_and_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.utcnow()

    portals = sa.table(
        "portals",
        sa.column("id", sa.Integer),
        sa.column("domain", sa.String),
        sa.column("account_id", sa.Integer),
        sa.column("admin_user_id", sa.Integer),
        sa.column("install_type", sa.String),
    )
    accounts = sa.table(
        "accounts",
        sa.column("id", sa.Integer),
        sa.column("account_no", sa.BigInteger),
        sa.column("name", sa.String),
        sa.column("status", sa.String),
        sa.column("owner_user_id", sa.Integer),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    web_users = sa.table(
        "web_users",
        sa.column("id", sa.Integer),
        sa.column("email", sa.String),
        sa.column("password_hash", sa.String),
        sa.column("portal_id", sa.Integer),
        sa.column("email_verified_at", sa.DateTime),
    )
    web_sessions = sa.table(
        "web_sessions",
        sa.column("id", sa.Integer),
        sa.column("user_id", sa.Integer),
        sa.column("app_user_id", sa.Integer),
    )
    app_users = sa.table(
        "app_users",
        sa.column("id", sa.Integer),
        sa.column("display_name", sa.String),
        sa.column("status", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    app_user_web_credentials = sa.table(
        "app_user_web_credentials",
        sa.column("user_id", sa.Integer),
        sa.column("login", sa.String),
        sa.column("email", sa.String),
        sa.column("password_hash", sa.String),
        sa.column("email_verified_at", sa.DateTime),
        sa.column("must_change_password", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    account_memberships = sa.table(
        "account_memberships",
        sa.column("id", sa.Integer),
        sa.column("account_id", sa.Integer),
        sa.column("user_id", sa.Integer),
        sa.column("role", sa.String),
        sa.column("status", sa.String),
        sa.column("invited_by_user_id", sa.Integer),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    account_permissions = sa.table(
        "account_permissions",
        sa.column("membership_id", sa.Integer),
        sa.column("kb_access", sa.String),
        sa.column("can_invite_users", sa.Boolean),
        sa.column("can_manage_settings", sa.Boolean),
        sa.column("can_view_finance", sa.Boolean),
        sa.column("updated_at", sa.DateTime),
    )
    account_integrations = sa.table(
        "account_integrations",
        sa.column("id", sa.Integer),
        sa.column("account_id", sa.Integer),
        sa.column("provider", sa.String),
        sa.column("status", sa.String),
        sa.column("external_key", sa.String),
        sa.column("portal_id", sa.Integer),
        sa.column("credentials_json", sa.JSON),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )

    max_account_no = bind.execute(sa.select(sa.func.max(accounts.c.account_no))).scalar()
    next_account_no = int(max_account_no or 100000) + 1

    portal_rows = bind.execute(
        sa.select(
            portals.c.id,
            portals.c.domain,
            portals.c.account_id,
            portals.c.admin_user_id,
            portals.c.install_type,
        )
    ).all()

    portal_account: dict[int, int] = {}
    portal_admin: dict[int, int | None] = {}

    for p in portal_rows:
        portal_admin[int(p.id)] = int(p.admin_user_id) if p.admin_user_id is not None else None
        if p.account_id is not None:
            portal_account[int(p.id)] = int(p.account_id)
            continue
        acc_id = bind.execute(
            accounts.insert()
            .values(
                account_no=next_account_no,
                name=(p.domain or "").strip() or None,
                status="active",
                owner_user_id=None,
                created_at=now,
                updated_at=now,
            )
            .returning(accounts.c.id)
        ).scalar_one()
        acc_id = int(acc_id)
        bind.execute(
            portals.update()
            .where(portals.c.id == p.id)
            .values(account_id=acc_id)
        )
        portal_account[int(p.id)] = acc_id
        next_account_no += 1

    credential_by_email: dict[str, int] = {}
    for row in bind.execute(sa.select(app_user_web_credentials.c.user_id, app_user_web_credentials.c.email)).all():
        email = (row.email or "").strip().lower()
        if email:
            credential_by_email[email] = int(row.user_id)

    existing_memberships = {
        (int(r.account_id), int(r.user_id)): int(r.id)
        for r in bind.execute(
            sa.select(account_memberships.c.id, account_memberships.c.account_id, account_memberships.c.user_id)
        ).all()
    }
    existing_permissions = {
        int(r.membership_id)
        for r in bind.execute(sa.select(account_permissions.c.membership_id)).all()
    }
    account_owner = {
        int(r.id): (int(r.owner_user_id) if r.owner_user_id is not None else None)
        for r in bind.execute(sa.select(accounts.c.id, accounts.c.owner_user_id)).all()
    }

    web_rows = bind.execute(
        sa.select(
            web_users.c.id,
            web_users.c.email,
            web_users.c.password_hash,
            web_users.c.portal_id,
            web_users.c.email_verified_at,
        )
    ).all()

    for w in web_rows:
        email = (w.email or "").strip().lower()
        if not email:
            continue
        app_user_id = credential_by_email.get(email)
        if app_user_id is None:
            app_user_id = bind.execute(
                app_users.insert()
                .values(
                    display_name=email,
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
                .returning(app_users.c.id)
            ).scalar_one()
            app_user_id = int(app_user_id)
            bind.execute(
                app_user_web_credentials.insert().values(
                    user_id=app_user_id,
                    login=email,
                    email=email,
                    password_hash=w.password_hash,
                    email_verified_at=w.email_verified_at,
                    must_change_password=False,
                    created_at=now,
                    updated_at=now,
                )
            )
            credential_by_email[email] = app_user_id

        bind.execute(
            web_sessions.update()
            .where(web_sessions.c.user_id == w.id)
            .values(app_user_id=app_user_id)
        )

        if w.portal_id is None:
            continue
        acc_id = portal_account.get(int(w.portal_id))
        if not acc_id:
            continue

        is_owner = portal_admin.get(int(w.portal_id)) == int(w.id)
        role = "owner" if is_owner else "member"
        key = (acc_id, app_user_id)

        membership_id = existing_memberships.get(key)
        if membership_id is None:
            membership_id = bind.execute(
                account_memberships.insert()
                .values(
                    account_id=acc_id,
                    user_id=app_user_id,
                    role=role,
                    status="active",
                    invited_by_user_id=None,
                    created_at=now,
                    updated_at=now,
                )
                .returning(account_memberships.c.id)
            ).scalar_one()
            membership_id = int(membership_id)
            existing_memberships[key] = membership_id
        elif is_owner:
            bind.execute(
                account_memberships.update()
                .where(account_memberships.c.id == membership_id)
                .values(role="owner", updated_at=now)
            )

        if membership_id not in existing_permissions:
            if role == "owner":
                bind.execute(
                    account_permissions.insert().values(
                        membership_id=membership_id,
                        kb_access="write",
                        can_invite_users=True,
                        can_manage_settings=True,
                        can_view_finance=True,
                        updated_at=now,
                    )
                )
            else:
                bind.execute(
                    account_permissions.insert().values(
                        membership_id=membership_id,
                        kb_access="read",
                        can_invite_users=False,
                        can_manage_settings=False,
                        can_view_finance=False,
                        updated_at=now,
                    )
                )
            existing_permissions.add(membership_id)

        if is_owner and account_owner.get(acc_id) is None:
            bind.execute(
                accounts.update()
                .where(accounts.c.id == acc_id)
                .values(owner_user_id=app_user_id, updated_at=now)
            )
            account_owner[acc_id] = app_user_id

    # Create bitrix integrations for existing bitrix portals.
    existing_integrations = {
        (str(r.provider or ""), str(r.external_key or ""))
        for r in bind.execute(sa.select(account_integrations.c.provider, account_integrations.c.external_key)).all()
    }
    for p in portal_rows:
        domain = (p.domain or "").strip().lower()
        if not domain:
            continue
        install_type = (p.install_type or "").strip().lower()
        is_bitrix = ("bitrix24." in domain) or install_type in ("local", "market")
        if not is_bitrix:
            continue
        k = ("bitrix", domain)
        if k in existing_integrations:
            continue
        acc_id = portal_account.get(int(p.id))
        if not acc_id:
            continue
        bind.execute(
            account_integrations.insert().values(
                account_id=acc_id,
                provider="bitrix",
                status="active",
                external_key=domain,
                portal_id=int(p.id),
                credentials_json=None,
                created_at=now,
                updated_at=now,
            )
        )
        existing_integrations.add(k)


def downgrade() -> None:
    # Data backfill is intentionally non-reversible.
    pass
