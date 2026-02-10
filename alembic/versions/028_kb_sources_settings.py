"""add kb sources settings

Revision ID: 028_kb_sources_settings
Revises: 027_merge_heads
Create Date: 2026-02-10 11:55:00
"""
from alembic import op
import sqlalchemy as sa


revision = "028_kb_sources_settings"
down_revision = "027_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("portal_kb_settings", sa.Column("show_sources", sa.Boolean(), nullable=True))
    op.add_column("portal_kb_settings", sa.Column("sources_format", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("portal_kb_settings", "sources_format")
    op.drop_column("portal_kb_settings", "show_sources")
