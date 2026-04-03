"""add account scope to kb chunks

Revision ID: 047_account_kb_chunk_scope
Revises: 046_account_kb_job_scope
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa

revision = "047_account_kb_chunk_scope"
down_revision = "046_account_kb_job_scope"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("kb_chunks", sa.Column("account_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_kb_chunks_account_id"), "kb_chunks", ["account_id"], unique=False)
    op.create_foreign_key(None, "kb_chunks", "accounts", ["account_id"], ["id"])

def downgrade() -> None:
    op.drop_constraint(None, "kb_chunks", type_="foreignkey")
    op.drop_index(op.f("ix_kb_chunks_account_id"), table_name="kb_chunks")
    op.drop_column("kb_chunks", "account_id")
