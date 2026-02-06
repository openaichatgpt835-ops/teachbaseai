"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-02-01

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "portals",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("domain", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("member_id", sa.String(64), index=True),
        sa.Column("status", sa.String(32), default="pending"),
        sa.Column("metadata_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "portal_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id"), nullable=False, index=True),
        sa.Column("access_token", sa.Text()),
        sa.Column("refresh_token", sa.Text()),
        sa.Column("expires_at", sa.DateTime()),
        sa.Column("scope", sa.String(512)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "portal_users_access",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "dialogs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id"), nullable=False, index=True),
        sa.Column("provider_dialog_id", sa.String(128), nullable=False, index=True),
        sa.Column("provider_dialog_id_raw", sa.String(256)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_dialogs_portal_provider", "dialogs", ["portal_id", "provider_dialog_id"])
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("dialog_id", sa.Integer(), sa.ForeignKey("dialogs.id"), nullable=False, index=True),
        sa.Column("provider_message_id", sa.String(128), index=True),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("body", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id"), nullable=False, index=True),
        sa.Column("provider_event_id", sa.String(128), index=True),
        sa.Column("event_type", sa.String(64)),
        sa.Column("payload_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_events_portal_provider", "events", ["portal_id", "provider_event_id"])
    op.create_table(
        "billing_plans",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("max_portals", sa.Integer()),
        sa.Column("max_dialogs", sa.Integer()),
        sa.Column("price", sa.Numeric(10, 2)),
    )
    op.create_table(
        "portal_billing",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id"), nullable=False, index=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("billing_plans.id"), index=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "usage_counters",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id"), nullable=False, index=True),
        sa.Column("counter_type", sa.String(32), nullable=False),
        sa.Column("value", sa.Integer(), default=0),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "outbox",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id"), nullable=False, index=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id"), index=True),
        sa.Column("status", sa.String(32), default="created"),
        sa.Column("retry_count", sa.Integer(), default=0),
        sa.Column("payload_json", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table("outbox")
    op.drop_table("usage_counters")
    op.drop_table("portal_billing")
    op.drop_table("billing_plans")
    op.drop_table("events")
    op.drop_table("messages")
    op.drop_table("dialogs")
    op.drop_table("portal_users_access")
    op.drop_table("portal_tokens")
    op.drop_table("portals")
    op.drop_table("admin_users")
