"""Add unique(portal_id, user_id) and created_by to portal_users_access

Revision ID: 004
Revises: 003
Create Date: 2026-02-01

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "portal_users_access",
        sa.Column("created_by_bitrix_user_id", sa.Integer(), nullable=True),
    )
    # Удаляем дубликаты (оставляем одну строку на пару portal_id, user_id)
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(sa.text("""
            DELETE FROM portal_users_access a
            WHERE EXISTS (
                SELECT 1 FROM portal_users_access b
                WHERE b.portal_id = a.portal_id AND b.user_id = a.user_id AND b.id < a.id
            )
        """))
    op.create_unique_constraint(
        "uq_portal_users_access_portal_user",
        "portal_users_access",
        ["portal_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_portal_users_access_portal_user",
        "portal_users_access",
        type_="unique",
    )
    op.drop_column("portal_users_access", "created_by_bitrix_user_id")
