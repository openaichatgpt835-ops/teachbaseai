"""web users + portal access display_name/kind

Revision ID: 024_web_users_and_portal_access
Revises: 023_bot_flow_and_dialog_state
Create Date: 2026-02-09
"""
from alembic import op
import sqlalchemy as sa


revision = "024_web_users_and_portal_access"
down_revision = "023_bot_flow_and_dialog_state"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "web_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_web_users_email", "web_users", ["email"], unique=True)
    op.create_index("ix_web_users_portal_id", "web_users", ["portal_id"], unique=False)

    op.create_table(
        "web_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("web_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_web_sessions_user_id", "web_sessions", ["user_id"], unique=False)
    op.create_index("ix_web_sessions_token", "web_sessions", ["token"], unique=True)

    op.add_column("portal_users_access", sa.Column("display_name", sa.String(length=128), nullable=True))
    op.add_column("portal_users_access", sa.Column("kind", sa.String(length=16), nullable=False, server_default="bitrix"))
    op.alter_column("portal_users_access", "kind", server_default=None)


def downgrade():
    op.drop_column("portal_users_access", "kind")
    op.drop_column("portal_users_access", "display_name")
    op.drop_index("ix_web_sessions_token", table_name="web_sessions")
    op.drop_index("ix_web_sessions_user_id", table_name="web_sessions")
    op.drop_table("web_sessions")
    op.drop_index("ix_web_users_portal_id", table_name="web_users")
    op.drop_index("ix_web_users_email", table_name="web_users")
    op.drop_table("web_users")
