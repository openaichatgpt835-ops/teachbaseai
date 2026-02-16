"""kb file query count

Revision ID: 030_kb_file_query_count
Revises: 029_kb_collections_and_uploader
Create Date: 2026-02-10
"""

from alembic import op
import sqlalchemy as sa


revision = "030_kb_file_query_count"
down_revision = "029_kb_collections_and_uploader"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kb_files", sa.Column("query_count", sa.Integer(), nullable=False, server_default="0"))
    op.alter_column("kb_files", "query_count", server_default=None)


def downgrade() -> None:
    op.drop_column("kb_files", "query_count")
