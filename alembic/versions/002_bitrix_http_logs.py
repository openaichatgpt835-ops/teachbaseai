"""Add bitrix_http_logs for trace

Revision ID: 002
Revises: 001
Create Date: 2026-02-01

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bitrix_http_logs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("trace_id", sa.String(64), index=True),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id"), index=True),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("method", sa.String(16)),
        sa.Column("path", sa.String(256)),
        sa.Column("summary_json", sa.Text()),
        sa.Column("status_code", sa.Integer()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_bitrix_http_logs_trace", "bitrix_http_logs", ["trace_id"])
    op.create_index("ix_bitrix_http_logs_portal_created", "bitrix_http_logs", ["portal_id", "created_at"])


def downgrade() -> None:
    op.drop_table("bitrix_http_logs")
