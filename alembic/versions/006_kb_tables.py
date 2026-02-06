"""Add vector_json to kb_embeddings for storing embedding vectors.

Revision ID: 012_kb_embeddings_vector_json
Revises: 011_portal_admin_user_id
Create Date: 2026-02-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "012_kb_embeddings_vector_json"
down_revision = "011_portal_admin_user_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kb_embeddings", sa.Column("vector_json", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("kb_embeddings", "vector_json")
