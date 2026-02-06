"""add portal_topic_summaries

Revision ID: 018_portal_topic_summaries
Revises: 017_kb_chunk_page_num
Create Date: 2026-02-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "018_portal_topic_summaries"
down_revision = "017_kb_chunk_page_num"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portal_topic_summaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id"), nullable=False, index=True),
        sa.Column("day", sa.Date(), nullable=False, index=True),
        sa.Column("source_from", sa.DateTime(), nullable=True),
        sa.Column("source_to", sa.DateTime(), nullable=True),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_portal_topic_summaries_portal_id ON portal_topic_summaries (portal_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_portal_topic_summaries_day ON portal_topic_summaries (day)")


def downgrade() -> None:
    op.drop_index("ix_portal_topic_summaries_day", table_name="portal_topic_summaries")
    op.drop_index("ix_portal_topic_summaries_portal_id", table_name="portal_topic_summaries")
    op.drop_table("portal_topic_summaries")
