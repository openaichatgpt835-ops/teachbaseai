"""add telegram settings and usernames

Revision ID: 021_portal_telegram_settings
Revises: 020_portal_kb_bot_settings
Create Date: 2026-02-08
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "021_portal_telegram_settings"
down_revision = "020_portal_kb_bot_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("portal_users_access", sa.Column("telegram_username", sa.String(length=64), nullable=True))
    op.create_unique_constraint(
        "uq_portal_users_access_telegram_username",
        "portal_users_access",
        ["portal_id", "telegram_username"],
    )
    op.create_table(
        "portal_telegram_settings",
        sa.Column("portal_id", sa.Integer(), nullable=False),
        sa.Column("staff_bot_token_enc", sa.Text(), nullable=True),
        sa.Column("staff_bot_secret", sa.String(length=64), nullable=True),
        sa.Column("staff_bot_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("client_bot_token_enc", sa.Text(), nullable=True),
        sa.Column("client_bot_secret", sa.String(length=64), nullable=True),
        sa.Column("client_bot_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["portal_id"], ["portals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("portal_id"),
    )


def downgrade() -> None:
    op.drop_table("portal_telegram_settings")
    op.drop_constraint("uq_portal_users_access_telegram_username", "portal_users_access", type_="unique")
    op.drop_column("portal_users_access", "telegram_username")
