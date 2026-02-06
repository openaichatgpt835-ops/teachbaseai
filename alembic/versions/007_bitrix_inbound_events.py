"""Add bitrix_inbound_events table for blackbox logging of POST /v1/bitrix/events.

Revision ID: 007
Revises: 006
Create Date: 2026-02-02

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bitrix_inbound_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id"), nullable=True),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("remote_ip", sa.Text(), nullable=True),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("path", sa.String(256), nullable=False),
        sa.Column("query", sa.Text(), nullable=True),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("headers_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("body_preview", sa.Text(), nullable=True),
        sa.Column("body_truncated", sa.Boolean(), nullable=False),
        sa.Column("body_sha256", sa.String(64), nullable=False),
        sa.Column("parsed_redacted_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("hints_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status_hint", sa.String(64), nullable=True),
    )
    op.create_index("idx_bitrix_inbound_events_created_at", "bitrix_inbound_events", ["created_at"])
    op.create_index("idx_bitrix_inbound_events_portal_created", "bitrix_inbound_events", ["portal_id", "created_at"])
    op.create_index("idx_bitrix_inbound_events_trace", "bitrix_inbound_events", ["trace_id"])
    op.create_index("idx_bitrix_inbound_events_domain_created", "bitrix_inbound_events", ["domain", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_bitrix_inbound_events_domain_created", table_name="bitrix_inbound_events")
    op.drop_index("idx_bitrix_inbound_events_trace", table_name="bitrix_inbound_events")
    op.drop_index("idx_bitrix_inbound_events_portal_created", table_name="bitrix_inbound_events")
    op.drop_index("idx_bitrix_inbound_events_created_at", table_name="bitrix_inbound_events")
    op.drop_table("bitrix_inbound_events")
