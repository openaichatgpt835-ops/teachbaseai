"""kb access levels v2

Revision ID: 052_kb_access_levels_v2
Revises: 051_kb_root_spaces
Create Date: 2026-04-06
"""

from alembic import op


revision = "052_kb_access_levels_v2"
down_revision = "051_kb_root_spaces"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE kb_folder_access SET access_level = 'edit' WHERE access_level = 'write'")
    op.execute("UPDATE kb_folder_access SET access_level = 'manage' WHERE access_level = 'admin'")

    op.execute("UPDATE kb_file_access SET access_level = 'edit' WHERE access_level = 'write'")
    op.execute("UPDATE kb_file_access SET access_level = 'manage' WHERE access_level = 'admin'")

    op.execute(
        """
        UPDATE account_permissions
        SET kb_access = 'manage'
        WHERE kb_access = 'write'
          AND membership_id IN (
            SELECT id FROM account_memberships WHERE role = 'owner'
          )
        """
    )
    op.execute("UPDATE account_permissions SET kb_access = 'edit' WHERE kb_access = 'write'")
    op.execute("UPDATE account_permissions SET kb_access = 'manage' WHERE kb_access = 'admin'")


def downgrade() -> None:
    op.execute("UPDATE kb_folder_access SET access_level = 'write' WHERE access_level IN ('upload', 'edit')")
    op.execute("UPDATE kb_folder_access SET access_level = 'admin' WHERE access_level = 'manage'")

    op.execute("UPDATE kb_file_access SET access_level = 'write' WHERE access_level IN ('upload', 'edit')")
    op.execute("UPDATE kb_file_access SET access_level = 'admin' WHERE access_level = 'manage'")

    op.execute(
        """
        UPDATE account_permissions
        SET kb_access = 'write'
        WHERE kb_access = 'manage'
          AND membership_id IN (
            SELECT id FROM account_memberships WHERE role = 'owner'
          )
        """
    )
    op.execute("UPDATE account_permissions SET kb_access = 'write' WHERE kb_access IN ('upload', 'edit')")
    op.execute("UPDATE account_permissions SET kb_access = 'admin' WHERE kb_access = 'manage'")
