"""account topic summaries

Revision ID: 043_account_topic_summaries
Revises: 042_account_kb_settings
Create Date: 2026-03-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "043_account_topic_summaries"
down_revision = "042_account_kb_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_topic_summaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("source_from", sa.DateTime(), nullable=True),
        sa.Column("source_to", sa.DateTime(), nullable=True),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_account_topic_summaries_account_id", "account_topic_summaries", ["account_id"])
    op.create_index("ix_account_topic_summaries_day", "account_topic_summaries", ["day"])

    op.execute(
        """
        INSERT INTO account_topic_summaries (account_id, day, source_from, source_to, items, created_at)
        SELECT p.account_id, pts.day, pts.source_from, pts.source_to, pts.items, pts.created_at
        FROM portal_topic_summaries pts
        JOIN portals p ON p.id = pts.portal_id
        WHERE p.account_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_account_topic_summaries_day", table_name="account_topic_summaries")
    op.drop_index("ix_account_topic_summaries_account_id", table_name="account_topic_summaries")
    op.drop_table("account_topic_summaries")
