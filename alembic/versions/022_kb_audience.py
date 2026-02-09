"""add kb audience columns

Revision ID: 022_kb_audience
Revises: 021_portal_telegram_settings
Create Date: 2026-02-08
"""
from alembic import op
import sqlalchemy as sa


revision = "022_kb_audience"
down_revision = "021_portal_telegram_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kb_sources", sa.Column("audience", sa.String(length=16), nullable=False, server_default="staff"))
    op.add_column("kb_files", sa.Column("audience", sa.String(length=16), nullable=False, server_default="staff"))
    op.add_column("kb_chunks", sa.Column("audience", sa.String(length=16), nullable=False, server_default="staff"))


def downgrade() -> None:
    op.drop_column("kb_chunks", "audience")
    op.drop_column("kb_files", "audience")
    op.drop_column("kb_sources", "audience")
