"""app users, memberships and permissions

Revision ID: 034_app_users_memberships
Revises: 033_accounts_core
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa


revision = "034_app_users_memberships"
down_revision = "033_accounts_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_app_users_status", "app_users", ["status"], unique=False)

    op.add_column("accounts", sa.Column("owner_user_id", sa.Integer(), nullable=True))
    op.create_index("ix_accounts_owner_user_id", "accounts", ["owner_user_id"], unique=False)
    op.create_foreign_key(
        "fk_accounts_owner_user_id_app_users",
        "accounts",
        "app_users",
        ["owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "app_user_web_credentials",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("login", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(), nullable=True),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("login", name="uq_app_user_web_credentials_login"),
        sa.UniqueConstraint("email", name="uq_app_user_web_credentials_email"),
    )
    op.create_index("ix_app_user_web_credentials_login", "app_user_web_credentials", ["login"], unique=False)
    op.create_index("ix_app_user_web_credentials_email", "app_user_web_credentials", ["email"], unique=False)

    op.create_table(
        "account_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="member"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("invited_by_user_id", sa.Integer(), sa.ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("account_id", "user_id", name="uq_account_memberships_account_user"),
    )
    op.create_index("ix_account_memberships_account_id", "account_memberships", ["account_id"], unique=False)
    op.create_index("ix_account_memberships_user_id", "account_memberships", ["user_id"], unique=False)
    op.create_index("ix_account_memberships_role", "account_memberships", ["role"], unique=False)
    op.create_index("ix_account_memberships_status", "account_memberships", ["status"], unique=False)

    op.create_table(
        "account_permissions",
        sa.Column("membership_id", sa.Integer(), sa.ForeignKey("account_memberships.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("kb_access", sa.String(length=16), nullable=False, server_default="none"),
        sa.Column("can_invite_users", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_manage_settings", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_view_finance", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.add_column("web_sessions", sa.Column("app_user_id", sa.Integer(), nullable=True))
    op.create_index("ix_web_sessions_app_user_id", "web_sessions", ["app_user_id"], unique=False)
    op.create_foreign_key(
        "fk_web_sessions_app_user_id_app_users",
        "web_sessions",
        "app_users",
        ["app_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.alter_column("app_users", "status", server_default=None)
    op.alter_column("app_user_web_credentials", "must_change_password", server_default=None)
    op.alter_column("account_memberships", "role", server_default=None)
    op.alter_column("account_memberships", "status", server_default=None)
    op.alter_column("account_permissions", "kb_access", server_default=None)
    op.alter_column("account_permissions", "can_invite_users", server_default=None)
    op.alter_column("account_permissions", "can_manage_settings", server_default=None)
    op.alter_column("account_permissions", "can_view_finance", server_default=None)


def downgrade() -> None:
    op.drop_constraint("fk_web_sessions_app_user_id_app_users", "web_sessions", type_="foreignkey")
    op.drop_index("ix_web_sessions_app_user_id", table_name="web_sessions")
    op.drop_column("web_sessions", "app_user_id")

    op.drop_table("account_permissions")

    op.drop_index("ix_account_memberships_status", table_name="account_memberships")
    op.drop_index("ix_account_memberships_role", table_name="account_memberships")
    op.drop_index("ix_account_memberships_user_id", table_name="account_memberships")
    op.drop_index("ix_account_memberships_account_id", table_name="account_memberships")
    op.drop_table("account_memberships")

    op.drop_index("ix_app_user_web_credentials_email", table_name="app_user_web_credentials")
    op.drop_index("ix_app_user_web_credentials_login", table_name="app_user_web_credentials")
    op.drop_table("app_user_web_credentials")

    op.drop_constraint("fk_accounts_owner_user_id_app_users", "accounts", type_="foreignkey")
    op.drop_index("ix_accounts_owner_user_id", table_name="accounts")
    op.drop_column("accounts", "owner_user_id")

    op.drop_index("ix_app_users_status", table_name="app_users")
    op.drop_table("app_users")
