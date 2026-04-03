"""kb root spaces

Revision ID: 051_kb_root_spaces
Revises: 050_account_user_group_kind
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa


revision = "051_kb_root_spaces"
down_revision = "050_account_user_group_kind"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kb_folders", sa.Column("root_space", sa.String(length=32), nullable=True))
    op.create_index("ix_kb_folders_root_space", "kb_folders", ["root_space"], unique=False)

    op.execute(
        """
        UPDATE kb_folders
        SET root_space = 'shared'
        WHERE parent_id IS NULL
          AND root_space IS NULL
          AND (
            lower(name) LIKE '%общ%'
            OR lower(name) LIKE '%shared%'
          )
        """
    )
    op.execute(
        """
        UPDATE kb_folders
        SET root_space = 'departments'
        WHERE parent_id IS NULL
          AND root_space IS NULL
          AND (
            lower(name) LIKE '%отдел%'
            OR lower(name) LIKE '%department%'
          )
        """
    )
    op.execute(
        """
        UPDATE kb_folders
        SET root_space = 'clients'
        WHERE parent_id IS NULL
          AND root_space IS NULL
          AND (
            lower(name) LIKE '%клиент%'
            OR lower(name) LIKE '%client%'
          )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_kb_folders_root_space", table_name="kb_folders")
    op.drop_column("kb_folders", "root_space")
