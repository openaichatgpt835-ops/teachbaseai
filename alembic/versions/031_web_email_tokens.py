"""web email tokens

Revision ID: 031_web_email_tokens
Revises: 030_kb_file_query_count
Create Date: 2026-02-10
"""

from alembic import op
import sqlalchemy as sa


revision = "031_web_email_tokens"
down_revision = "030_kb_file_query_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "web_email_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("web_users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("token", sa.String(length=128), nullable=False, unique=True, index=True),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="confirm"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("used_at", sa.DateTime(), nullable=True),
    )
    op.alter_column("web_email_tokens", "kind", server_default=None)


def downgrade() -> None:
    op.drop_table("web_email_tokens")
