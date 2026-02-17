"""kb pgvector column and index

Revision ID: 032_kb_pgvector
Revises: 031_web_email_tokens
Create Date: 2026-02-17
"""

from alembic import op
import sqlalchemy as sa


revision = "032_kb_pgvector"
down_revision = "031_web_email_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    has_vector = bind.execute(
        sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector' LIMIT 1")
    ).scalar()
    if not has_vector:
        # pgvector package is not installed on this postgres host yet.
        return

    # Extension may already exist; keep upgrade idempotent.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # 1024 covers current embedding models and keeps room for growth.
    op.execute("ALTER TABLE kb_embeddings ADD COLUMN IF NOT EXISTS vector_pg vector(1024)")
    # IVF index speeds ANN queries for cosine distance.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_kb_embeddings_vector_pg_ivfflat
        ON kb_embeddings
        USING ivfflat (vector_pg vector_cosine_ops)
        """
    )
    # Existing btree model/chunk indexes stay as-is.


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_kb_embeddings_vector_pg_ivfflat")
    op.execute("ALTER TABLE kb_embeddings DROP COLUMN IF EXISTS vector_pg")
