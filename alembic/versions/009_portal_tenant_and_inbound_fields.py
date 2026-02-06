"""Add portal member_id/application_token/install_type unique indexes and inbound event fields.

Revision ID: 009
Revises: 008
Create Date: 2026-02-03
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("portals", sa.Column("application_token", sa.String(128), nullable=True))
    op.add_column("portals", sa.Column("install_type", sa.String(16), nullable=True))
    op.execute("UPDATE portals SET member_id = NULL WHERE member_id IS NOT NULL AND btrim(member_id) = ''")
    op.execute("UPDATE portals SET application_token = NULL WHERE application_token IS NOT NULL AND btrim(application_token) = ''")
    op.create_index(
        "uq_portals_member_id",
        "portals",
        ["member_id"],
        unique=True,
        postgresql_where=sa.text("member_id IS NOT NULL"),
    )
    op.create_index(
        "uq_portals_application_token",
        "portals",
        ["application_token"],
        unique=True,
        postgresql_where=sa.text("application_token IS NOT NULL"),
    )

    op.add_column("bitrix_inbound_events", sa.Column("member_id", sa.String(64), nullable=True))
    op.add_column("bitrix_inbound_events", sa.Column("dialog_id", sa.String(128), nullable=True))
    op.add_column("bitrix_inbound_events", sa.Column("user_id", sa.String(64), nullable=True))
    op.add_column("bitrix_inbound_events", sa.Column("event_name", sa.String(128), nullable=True))
    op.create_index("idx_bitrix_inbound_events_member", "bitrix_inbound_events", ["member_id"])
    op.create_index("idx_bitrix_inbound_events_dialog", "bitrix_inbound_events", ["dialog_id"])
    op.create_index("idx_bitrix_inbound_events_event", "bitrix_inbound_events", ["event_name"])


def downgrade() -> None:
    op.drop_index("idx_bitrix_inbound_events_event", table_name="bitrix_inbound_events")
    op.drop_index("idx_bitrix_inbound_events_dialog", table_name="bitrix_inbound_events")
    op.drop_index("idx_bitrix_inbound_events_member", table_name="bitrix_inbound_events")
    op.drop_column("bitrix_inbound_events", "event_name")
    op.drop_column("bitrix_inbound_events", "user_id")
    op.drop_column("bitrix_inbound_events", "dialog_id")
    op.drop_column("bitrix_inbound_events", "member_id")

    op.drop_index("uq_portals_application_token", table_name="portals")
    op.drop_index("uq_portals_member_id", table_name="portals")
    op.drop_column("portals", "install_type")
    op.drop_column("portals", "application_token")
