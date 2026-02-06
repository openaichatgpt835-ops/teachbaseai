"""add dialog rag cache

Revision ID: 019_dialog_rag_cache
Revises: 018_portal_topic_summaries
Create Date: 2026-02-06
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "019_dialog_rag_cache"
down_revision = "018_portal_topic_summaries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dialog_rag_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dialog_id", sa.Integer(), sa.ForeignKey("dialogs.id"), nullable=False),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id"), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("chunk_ids_json", sa.Text(), nullable=True),
        sa.Column("keywords_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_dialog_rag_cache_dialog_id", "dialog_rag_cache", ["dialog_id"])
    op.create_index("ix_dialog_rag_cache_portal_id", "dialog_rag_cache", ["portal_id"])
    op.create_index("ix_dialog_rag_cache_model", "dialog_rag_cache", ["model"])
    op.create_index(
        "ix_dialog_rag_cache_dialog_model",
        "dialog_rag_cache",
        ["dialog_id", "model"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_dialog_rag_cache_dialog_model", table_name="dialog_rag_cache")
    op.drop_index("ix_dialog_rag_cache_model", table_name="dialog_rag_cache")
    op.drop_index("ix_dialog_rag_cache_portal_id", table_name="dialog_rag_cache")
    op.drop_index("ix_dialog_rag_cache_dialog_id", table_name="dialog_rag_cache")
    op.drop_table("dialog_rag_cache")
