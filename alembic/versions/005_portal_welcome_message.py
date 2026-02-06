"""Add portals.welcome_message for per-portal welcome text.

Revision ID: 005
Revises: 004
Create Date: 2026-02-02

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_WELCOME = "Привет! Я Teachbase AI. Напишите «ping» — отвечу «pong»."


def upgrade() -> None:
    op.add_column(
        "portals",
        sa.Column("welcome_message", sa.Text(), nullable=True),
    )
    escaped = DEFAULT_WELCOME.replace("'", "''")
    op.execute(sa.text("UPDATE portals SET welcome_message = '" + escaped + "' WHERE welcome_message IS NULL"))
    op.alter_column(
        "portals",
        "welcome_message",
        existing_type=sa.Text(),
        nullable=False,
        server_default=sa.text("'" + escaped + "'"),
    )


def downgrade() -> None:
    op.drop_column("portals", "welcome_message")
