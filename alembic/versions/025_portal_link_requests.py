"""portal link requests

Revision ID: 025_portal_link_requests
Revises: 024_web_users_and_portal_access
Create Date: 2026-02-09 18:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "025_portal_link_requests"
down_revision = "024_web_users_and_portal_access"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "portal_link_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("web_user_id", sa.Integer(), sa.ForeignKey("web_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_portal_id", sa.Integer(), sa.ForeignKey("portals.id"), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("merge_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_portal_link_requests_portal_id", "portal_link_requests", ["portal_id"])
    op.create_index("ix_portal_link_requests_web_user_id", "portal_link_requests", ["web_user_id"])
    op.create_index("ix_portal_link_requests_source_portal_id", "portal_link_requests", ["source_portal_id"])


def downgrade():
    op.drop_index("ix_portal_link_requests_source_portal_id", table_name="portal_link_requests")
    op.drop_index("ix_portal_link_requests_web_user_id", table_name="portal_link_requests")
    op.drop_index("ix_portal_link_requests_portal_id", table_name="portal_link_requests")
    op.drop_table("portal_link_requests")
