"""account user groups kind

Revision ID: 050_account_user_group_kind
Revises: 049_account_user_groups
Create Date: 2026-04-01
"""

from alembic import op
import sqlalchemy as sa


revision = "050_account_user_group_kind"
down_revision = "049_account_user_groups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "account_user_groups",
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="staff"),
    )
    op.execute("UPDATE account_user_groups SET kind = 'staff' WHERE kind IS NULL")
    op.alter_column("account_user_groups", "kind", server_default=None)


def downgrade() -> None:
    op.drop_column("account_user_groups", "kind")
