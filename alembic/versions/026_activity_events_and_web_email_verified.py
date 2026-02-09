"""activity events and web email verified

Revision ID: 026_activity_events_web_email
Revises: 025_portal_link_requests
Create Date: 2026-02-09 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "026_activity_events_web_email"
down_revision = "025_portal_link_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("web_users", sa.Column("email_verified_at", sa.DateTime(), nullable=True))

    op.create_table(
        "activity_events",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id"), nullable=True),
        sa.Column("web_user_id", sa.Integer(), sa.ForeignKey("web_users.id"), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_activity_events_kind_time", "activity_events", ["kind", "created_at"])
    op.create_index("ix_activity_events_portal_id", "activity_events", ["portal_id"])
    op.create_index("ix_activity_events_web_user_id", "activity_events", ["web_user_id"])


def downgrade() -> None:
    op.drop_index("ix_activity_events_web_user_id", table_name="activity_events")
    op.drop_index("ix_activity_events_portal_id", table_name="activity_events")
    op.drop_index("ix_activity_events_kind_time", table_name="activity_events")
    op.drop_table("activity_events")
    op.drop_column("web_users", "email_verified_at")
