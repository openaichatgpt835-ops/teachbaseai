"""add page number to kb chunks

Revision ID: 017_kb_chunk_page_num
Revises: 016_portal_kb_prompt_preset
Create Date: 2026-02-06
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "017_kb_chunk_page_num"
down_revision = "016_portal_kb_prompt_preset"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kb_chunks", sa.Column("page_num", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("kb_chunks", "page_num")
