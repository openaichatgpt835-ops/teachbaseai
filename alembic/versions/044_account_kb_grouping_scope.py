"""account kb grouping scope

Revision ID: 044_account_kb_grouping_scope
Revises: 043_account_topic_summaries
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa


revision = "044_account_kb_grouping_scope"
down_revision = "043_account_topic_summaries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kb_collections", sa.Column("account_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_kb_collections_account_id"), "kb_collections", ["account_id"], unique=False)
    op.create_foreign_key(
        "fk_kb_collections_account_id_accounts",
        "kb_collections",
        "accounts",
        ["account_id"],
        ["id"],
    )

    op.add_column("kb_smart_folders", sa.Column("account_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_kb_smart_folders_account_id"), "kb_smart_folders", ["account_id"], unique=False)
    op.create_foreign_key(
        "fk_kb_smart_folders_account_id_accounts",
        "kb_smart_folders",
        "accounts",
        ["account_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_kb_smart_folders_account_id_accounts", "kb_smart_folders", type_="foreignkey")
    op.drop_index(op.f("ix_kb_smart_folders_account_id"), table_name="kb_smart_folders")
    op.drop_column("kb_smart_folders", "account_id")

    op.drop_constraint("fk_kb_collections_account_id_accounts", "kb_collections", type_="foreignkey")
    op.drop_index(op.f("ix_kb_collections_account_id"), table_name="kb_collections")
    op.drop_column("kb_collections", "account_id")
