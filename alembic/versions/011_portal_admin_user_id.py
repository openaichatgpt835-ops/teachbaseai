"""portal admin user id

Revision ID: 011_portal_admin_user_id
Revises: 010_kb_tables
Create Date: 2026-02-04 15:10:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "011_portal_admin_user_id"
down_revision = "010_kb_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("portals", sa.Column("admin_user_id", sa.Integer(), nullable=True))
    op.create_index("ix_portals_admin_user_id", "portals", ["admin_user_id"])


def downgrade() -> None:
    op.drop_index("ix_portals_admin_user_id", table_name="portals")
    op.drop_column("portals", "admin_user_id")
