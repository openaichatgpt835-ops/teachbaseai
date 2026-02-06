"""add kb_chunk timecodes

Revision ID: 014_kb_chunk_timecodes
Revises: 013_portal_kb_settings
Create Date: 2026-02-05
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "014_kb_chunk_timecodes"
down_revision = "013_portal_kb_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kb_chunks", sa.Column("start_ms", sa.Integer(), nullable=True))
    op.add_column("kb_chunks", sa.Column("end_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("kb_chunks", "end_ms")
    op.drop_column("kb_chunks", "start_ms")
