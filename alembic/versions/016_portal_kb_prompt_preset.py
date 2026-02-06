"""add portal kb prompt preset

Revision ID: 016_portal_kb_prompt_preset
Revises: 015_billing_usage_limits
Create Date: 2026-02-05
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "016_portal_kb_prompt_preset"
down_revision = "015_billing_usage_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("portal_kb_settings", sa.Column("prompt_preset", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("portal_kb_settings", "prompt_preset")
