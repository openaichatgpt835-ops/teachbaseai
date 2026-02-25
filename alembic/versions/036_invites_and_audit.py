"""account invites and audit log

Revision ID: 036_invites_and_audit
Revises: 035_integrations_and_identities
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "036_invites_and_audit"
down_revision = "035_integrations_and_identities"
branch_labels = None
depends_on = None


def _json_type(bind):
    return postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == "postgresql" else sa.JSON()


def upgrade() -> None:
    bind = op.get_bind()
    json_t = _json_type(bind)

    op.create_table(
        "account_invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("login", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="member"),
        sa.Column("permissions_json", json_t, nullable=True),
        sa.Column("token", sa.String(length=128), nullable=False, unique=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("invited_by_user_id", sa.Integer(), sa.ForeignKey("app_users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("accepted_user_id", sa.Integer(), sa.ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_account_invites_account_id", "account_invites", ["account_id"], unique=False)
    op.create_index("ix_account_invites_email", "account_invites", ["email"], unique=False)
    op.create_index("ix_account_invites_login", "account_invites", ["login"], unique=False)
    op.create_index("ix_account_invites_status", "account_invites", ["status"], unique=False)
    op.create_index("ix_account_invites_token", "account_invites", ["token"], unique=True)
    op.create_index("ix_account_invites_invited_by_user_id", "account_invites", ["invited_by_user_id"], unique=False)
    op.create_index("ix_account_invites_accepted_user_id", "account_invites", ["accepted_user_id"], unique=False)

    op.create_table(
        "account_audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("subject_type", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("payload_json", json_t, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_account_audit_log_account_id", "account_audit_log", ["account_id"], unique=False)
    op.create_index("ix_account_audit_log_actor_user_id", "account_audit_log", ["actor_user_id"], unique=False)
    op.create_index("ix_account_audit_log_event_type", "account_audit_log", ["event_type"], unique=False)
    op.create_index("ix_account_audit_log_subject_type", "account_audit_log", ["subject_type"], unique=False)
    op.create_index("ix_account_audit_log_subject_id", "account_audit_log", ["subject_id"], unique=False)
    op.create_index("ix_account_audit_log_created_at", "account_audit_log", ["created_at"], unique=False)
    op.create_index("ix_account_audit_log_account_created", "account_audit_log", ["account_id", "created_at"], unique=False)

    op.alter_column("account_invites", "role", server_default=None)
    op.alter_column("account_invites", "status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_account_audit_log_account_created", table_name="account_audit_log")
    op.drop_index("ix_account_audit_log_created_at", table_name="account_audit_log")
    op.drop_index("ix_account_audit_log_subject_id", table_name="account_audit_log")
    op.drop_index("ix_account_audit_log_subject_type", table_name="account_audit_log")
    op.drop_index("ix_account_audit_log_event_type", table_name="account_audit_log")
    op.drop_index("ix_account_audit_log_actor_user_id", table_name="account_audit_log")
    op.drop_index("ix_account_audit_log_account_id", table_name="account_audit_log")
    op.drop_table("account_audit_log")

    op.drop_index("ix_account_invites_accepted_user_id", table_name="account_invites")
    op.drop_index("ix_account_invites_invited_by_user_id", table_name="account_invites")
    op.drop_index("ix_account_invites_token", table_name="account_invites")
    op.drop_index("ix_account_invites_status", table_name="account_invites")
    op.drop_index("ix_account_invites_login", table_name="account_invites")
    op.drop_index("ix_account_invites_email", table_name="account_invites")
    op.drop_index("ix_account_invites_account_id", table_name="account_invites")
    op.drop_table("account_invites")
