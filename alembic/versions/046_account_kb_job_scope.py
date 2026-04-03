"""add account scope to kb jobs

Revision ID: 046_account_kb_job_scope
Revises: 045_account_kb_resource_scope
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa

revision = "046_account_kb_job_scope"
down_revision = "045_account_kb_resource_scope"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("kb_jobs", sa.Column("account_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_kb_jobs_account_id"), "kb_jobs", ["account_id"], unique=False)
    op.create_foreign_key(None, "kb_jobs", "accounts", ["account_id"], ["id"])

def downgrade() -> None:
    op.drop_constraint(None, "kb_jobs", type_="foreignkey")
    op.drop_index(op.f("ix_kb_jobs_account_id"), table_name="kb_jobs")
    op.drop_column("kb_jobs", "account_id")
