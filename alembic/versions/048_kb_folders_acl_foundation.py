"""kb folders and acl foundation

Revision ID: 048_kb_folders_acl_foundation
Revises: 047_account_kb_chunk_scope
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa

revision = "048_kb_folders_acl_foundation"
down_revision = "047_account_kb_chunk_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kb_folders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("portal_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["kb_folders.id"]),
        sa.ForeignKeyConstraint(["portal_id"], ["portals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kb_folders_id"), "kb_folders", ["id"], unique=False)
    op.create_index(op.f("ix_kb_folders_account_id"), "kb_folders", ["account_id"], unique=False)
    op.create_index(op.f("ix_kb_folders_portal_id"), "kb_folders", ["portal_id"], unique=False)
    op.create_index(op.f("ix_kb_folders_parent_id"), "kb_folders", ["parent_id"], unique=False)
    op.create_index("ix_kb_folders_account_parent", "kb_folders", ["account_id", "parent_id"], unique=False)
    op.create_index("ix_kb_folders_portal_parent", "kb_folders", ["portal_id", "parent_id"], unique=False)

    op.add_column("kb_files", sa.Column("folder_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_kb_files_folder_id"), "kb_files", ["folder_id"], unique=False)
    op.create_foreign_key(None, "kb_files", "kb_folders", ["folder_id"], ["id"])

    op.create_table(
        "kb_folder_access",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("folder_id", sa.Integer(), nullable=False),
        sa.Column("principal_type", sa.String(length=32), nullable=False),
        sa.Column("principal_id", sa.String(length=128), nullable=False),
        sa.Column("access_level", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["folder_id"], ["kb_folders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kb_folder_access_id"), "kb_folder_access", ["id"], unique=False)
    op.create_index(op.f("ix_kb_folder_access_folder_id"), "kb_folder_access", ["folder_id"], unique=False)
    op.create_index(
        "ix_kb_folder_access_folder_principal",
        "kb_folder_access",
        ["folder_id", "principal_type", "principal_id"],
        unique=False,
    )

    op.create_table(
        "kb_file_access",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("principal_type", sa.String(length=32), nullable=False),
        sa.Column("principal_id", sa.String(length=128), nullable=False),
        sa.Column("access_level", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["kb_files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kb_file_access_id"), "kb_file_access", ["id"], unique=False)
    op.create_index(op.f("ix_kb_file_access_file_id"), "kb_file_access", ["file_id"], unique=False)
    op.create_index(
        "ix_kb_file_access_file_principal",
        "kb_file_access",
        ["file_id", "principal_type", "principal_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_kb_file_access_file_principal", table_name="kb_file_access")
    op.drop_index(op.f("ix_kb_file_access_file_id"), table_name="kb_file_access")
    op.drop_index(op.f("ix_kb_file_access_id"), table_name="kb_file_access")
    op.drop_table("kb_file_access")

    op.drop_index("ix_kb_folder_access_folder_principal", table_name="kb_folder_access")
    op.drop_index(op.f("ix_kb_folder_access_folder_id"), table_name="kb_folder_access")
    op.drop_index(op.f("ix_kb_folder_access_id"), table_name="kb_folder_access")
    op.drop_table("kb_folder_access")

    op.drop_constraint(None, "kb_files", type_="foreignkey")
    op.drop_index(op.f("ix_kb_files_folder_id"), table_name="kb_files")
    op.drop_column("kb_files", "folder_id")

    op.drop_index("ix_kb_folders_portal_parent", table_name="kb_folders")
    op.drop_index("ix_kb_folders_account_parent", table_name="kb_folders")
    op.drop_index(op.f("ix_kb_folders_parent_id"), table_name="kb_folders")
    op.drop_index(op.f("ix_kb_folders_portal_id"), table_name="kb_folders")
    op.drop_index(op.f("ix_kb_folders_account_id"), table_name="kb_folders")
    op.drop_index(op.f("ix_kb_folders_id"), table_name="kb_folders")
    op.drop_table("kb_folders")
