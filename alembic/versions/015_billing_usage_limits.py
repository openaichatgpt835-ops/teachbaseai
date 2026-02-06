"""add billing usage and limits

Revision ID: 015_billing_usage_limits
Revises: 014_kb_chunk_timecodes
Create Date: 2026-02-05
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "015_billing_usage_limits"
down_revision = "014_kb_chunk_timecodes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portal_usage_limits",
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id"), primary_key=True),
        sa.Column("monthly_request_limit", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "billing_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(length=64), nullable=True, index=True),
        sa.Column("request_id", sa.String(length=128), nullable=True, index=True),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="chat"),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("tokens_prompt", sa.Integer(), nullable=True),
        sa.Column("tokens_completion", sa.Integer(), nullable=True),
        sa.Column("tokens_total", sa.Integer(), nullable=True),
        sa.Column("cost_rub", sa.Numeric(12, 6), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ok"),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("billing_usage")
    op.drop_table("portal_usage_limits")
