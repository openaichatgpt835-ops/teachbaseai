"""add account scope to kb files and sources

Revision ID: 045_account_kb_resource_scope
Revises: 044_account_kb_grouping_scope
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa


revision = "045_account_kb_resource_scope"
down_revision = "044_account_kb_grouping_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kb_sources", sa.Column("account_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_kb_sources_account_id"), "kb_sources", ["account_id"], unique=False)
    op.create_foreign_key(None, "kb_sources", "accounts", ["account_id"], ["id"])

    op.add_column("kb_files", sa.Column("account_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_kb_files_account_id"), "kb_files", ["account_id"], unique=False)
    op.create_foreign_key(None, "kb_files", "accounts", ["account_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint(None, "kb_files", type_="foreignkey")
    op.drop_index(op.f("ix_kb_files_account_id"), table_name="kb_files")
    op.drop_column("kb_files", "account_id")

    op.drop_constraint(None, "kb_sources", type_="foreignkey")
    op.drop_index(op.f("ix_kb_sources_account_id"), table_name="kb_sources")
    op.drop_column("kb_sources", "account_id")
