"""add portal_kb_settings

Revision ID: 013_portal_kb_settings
Revises: 012_kb_embeddings_vector_json
Create Date: 2026-02-05
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "013_portal_kb_settings"
down_revision = "012_kb_embeddings_vector_json"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portal_kb_settings",
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id"), primary_key=True),
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
        sa.Column("chat_model", sa.String(length=255), nullable=True),
        sa.Column("api_base", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("portal_kb_settings")
