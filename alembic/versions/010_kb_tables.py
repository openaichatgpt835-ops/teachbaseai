"""kb tables

Revision ID: 010_kb_tables
Revises: 009
Create Date: 2026-02-04 12:30:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "010_kb_tables"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kb_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id"), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("title", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_kb_sources_portal_id", "kb_sources", ["portal_id"])

    op.create_table(
        "kb_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id"), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("kb_sources.id"), nullable=True),
        sa.Column("filename", sa.String(length=256), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="uploaded"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_kb_files_portal_id", "kb_files", ["portal_id"])
    op.create_index("ix_kb_files_source_id", "kb_files", ["source_id"])
    op.create_index("ix_kb_files_sha256", "kb_files", ["sha256"])
    op.create_index("ix_kb_files_portal_status", "kb_files", ["portal_id", "status"])

    op.create_table(
        "kb_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id"), nullable=False),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("kb_files.id"), nullable=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("kb_sources.id"), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("lang", sa.String(length=16), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_kb_chunks_portal_id", "kb_chunks", ["portal_id"])
    op.create_index("ix_kb_chunks_file_id", "kb_chunks", ["file_id"])
    op.create_index("ix_kb_chunks_source_id", "kb_chunks", ["source_id"])
    op.create_index("ix_kb_chunks_sha256", "kb_chunks", ["sha256"])
    op.create_index("ix_kb_chunks_portal_file_idx", "kb_chunks", ["portal_id", "file_id", "chunk_index"])

    op.create_table(
        "kb_embeddings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chunk_id", sa.Integer(), sa.ForeignKey("kb_chunks.id"), nullable=False),
        sa.Column("vector_id", sa.String(length=128), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("dim", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_kb_embeddings_chunk_id", "kb_embeddings", ["chunk_id"])
    op.create_index("ix_kb_embeddings_vector_id", "kb_embeddings", ["vector_id"])

    op.create_table(
        "kb_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id"), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_kb_jobs_portal_id", "kb_jobs", ["portal_id"])
    op.create_index("ix_kb_jobs_trace_id", "kb_jobs", ["trace_id"])
    op.create_index("ix_kb_jobs_portal_status", "kb_jobs", ["portal_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_kb_jobs_portal_status", table_name="kb_jobs")
    op.drop_index("ix_kb_jobs_trace_id", table_name="kb_jobs")
    op.drop_index("ix_kb_jobs_portal_id", table_name="kb_jobs")
    op.drop_table("kb_jobs")

    op.drop_index("ix_kb_embeddings_vector_id", table_name="kb_embeddings")
    op.drop_index("ix_kb_embeddings_chunk_id", table_name="kb_embeddings")
    op.drop_table("kb_embeddings")

    op.drop_index("ix_kb_chunks_portal_file_idx", table_name="kb_chunks")
    op.drop_index("ix_kb_chunks_sha256", table_name="kb_chunks")
    op.drop_index("ix_kb_chunks_source_id", table_name="kb_chunks")
    op.drop_index("ix_kb_chunks_file_id", table_name="kb_chunks")
    op.drop_index("ix_kb_chunks_portal_id", table_name="kb_chunks")
    op.drop_table("kb_chunks")

    op.drop_index("ix_kb_files_portal_status", table_name="kb_files")
    op.drop_index("ix_kb_files_sha256", table_name="kb_files")
    op.drop_index("ix_kb_files_source_id", table_name="kb_files")
    op.drop_index("ix_kb_files_portal_id", table_name="kb_files")
    op.drop_table("kb_files")

    op.drop_index("ix_kb_sources_portal_id", table_name="kb_sources")
    op.drop_table("kb_sources")
