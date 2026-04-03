"""account user groups foundation

Revision ID: 049_account_user_groups
Revises: 048_kb_folders_acl_foundation
Create Date: 2026-04-01
"""

from alembic import op
import sqlalchemy as sa


revision = "049_account_user_groups"
down_revision = "048_kb_folders_acl_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_user_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("account_id", "name", name="uq_account_user_groups_account_name"),
    )
    op.create_index("ix_account_user_groups_account_id", "account_user_groups", ["account_id"])

    op.create_table(
        "account_user_group_members",
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("account_user_groups.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("membership_id", sa.Integer(), sa.ForeignKey("account_memberships.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_account_user_group_members_membership_id", "account_user_group_members", ["membership_id"])


def downgrade() -> None:
    op.drop_index("ix_account_user_group_members_membership_id", table_name="account_user_group_members")
    op.drop_table("account_user_group_members")
    op.drop_index("ix_account_user_groups_account_id", table_name="account_user_groups")
    op.drop_table("account_user_groups")
