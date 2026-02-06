"""Add last_welcome_at, last_welcome_hash to portal_users_access for idempotent welcome.

Revision ID: 006
Revises: 005
Create Date: 2026-02-02

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "portal_users_access",
        sa.Column("last_welcome_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "portal_users_access",
        sa.Column("last_welcome_hash", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("portal_users_access", "last_welcome_hash")
    op.drop_column("portal_users_access", "last_welcome_at")
