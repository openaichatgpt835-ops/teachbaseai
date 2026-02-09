"""add portal bot flows and dialog states

Revision ID: 023_bot_flow_and_dialog_state
Revises: 022_kb_audience
Create Date: 2026-02-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "023_bot_flow_and_dialog_state"
down_revision = "022_kb_audience"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portal_bot_flows",
        sa.Column("portal_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("draft_json", postgresql.JSONB(), nullable=True),
        sa.Column("published_json", postgresql.JSONB(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["portal_id"], ["portals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("portal_id", "kind"),
    )
    op.create_table(
        "dialog_states",
        sa.Column("dialog_id", sa.Integer(), nullable=False),
        sa.Column("state_json", postgresql.JSONB(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["dialog_id"], ["dialogs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("dialog_id"),
    )


def downgrade() -> None:
    op.drop_table("dialog_states")
    op.drop_table("portal_bot_flows")
