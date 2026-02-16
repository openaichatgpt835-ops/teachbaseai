"""kb collections, smart folders, uploader meta

Revision ID: 029_kb_collections_and_uploader
Revises: 028_kb_sources_settings
Create Date: 2026-02-10 12:18:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "029_kb_collections_and_uploader"
down_revision = "028_kb_sources_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kb_files", sa.Column("uploaded_by_type", sa.String(length=32), nullable=True))
    op.add_column("kb_files", sa.Column("uploaded_by_id", sa.String(length=64), nullable=True))
    op.add_column("kb_files", sa.Column("uploaded_by_name", sa.String(length=128), nullable=True))

    op.create_table(
        "kb_collections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id"), nullable=False, index=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("color", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "kb_collection_files",
        sa.Column("collection_id", sa.Integer(), sa.ForeignKey("kb_collections.id"), primary_key=True),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("kb_files.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_kb_collection_files_file", "kb_collection_files", ["file_id"])
    op.create_table(
        "kb_smart_folders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id"), nullable=False, index=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("system_tag", sa.String(length=64), nullable=True),
        sa.Column("rules_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.add_column("portal_kb_settings", sa.Column("collections_multi_assign", sa.Boolean(), nullable=True))
    op.add_column("portal_kb_settings", sa.Column("smart_folder_threshold", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("portal_kb_settings", "smart_folder_threshold")
    op.drop_column("portal_kb_settings", "collections_multi_assign")

    op.drop_table("kb_smart_folders")
    op.drop_index("ix_kb_collection_files_file", table_name="kb_collection_files")
    op.drop_table("kb_collection_files")
    op.drop_table("kb_collections")

    op.drop_column("kb_files", "uploaded_by_name")
    op.drop_column("kb_files", "uploaded_by_id")
    op.drop_column("kb_files", "uploaded_by_type")
