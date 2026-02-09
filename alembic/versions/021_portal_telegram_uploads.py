"""add telegram upload flags

Revision ID: 021_portal_telegram_uploads
Revises: 020_portal_kb_bot_settings
Create Date: 2026-02-09
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "021_portal_telegram_uploads"
down_revision = "020_portal_kb_bot_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "portal_telegram_settings",
        sa.Column("staff_allow_uploads", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "portal_telegram_settings",
        sa.Column("client_allow_uploads", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.alter_column("portal_telegram_settings", "staff_allow_uploads", server_default=None)
    op.alter_column("portal_telegram_settings", "client_allow_uploads", server_default=None)


def downgrade() -> None:
    op.drop_column("portal_telegram_settings", "client_allow_uploads")
    op.drop_column("portal_telegram_settings", "staff_allow_uploads")
