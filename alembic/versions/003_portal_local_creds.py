"""Add portal local_client_id and local_client_secret_encrypted for Local App

Revision ID: 003
Revises: 002
Create Date: 2026-02-01

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("portals", sa.Column("local_client_id", sa.String(128), nullable=True))
    op.add_column("portals", sa.Column("local_client_secret_encrypted", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("portals", "local_client_secret_encrypted")
    op.drop_column("portals", "local_client_id")
