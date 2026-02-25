"""media transcription option and file transcript fields

Revision ID: 038_media_transcription_option
Revises: 037_backfill_accounts_rbac
Create Date: 2026-02-24
"""

from alembic import op
import sqlalchemy as sa


revision = "038_media_transcription_option"
down_revision = "037_backfill_accounts_rbac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("portal_kb_settings") as batch_op:
        batch_op.add_column(sa.Column("media_transcription_enabled", sa.Boolean(), nullable=True))

    with op.batch_alter_table("kb_files") as batch_op:
        batch_op.add_column(sa.Column("transcript_status", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("transcript_error", sa.Text(), nullable=True))

    op.execute("UPDATE portal_kb_settings SET media_transcription_enabled = TRUE WHERE media_transcription_enabled IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("kb_files") as batch_op:
        batch_op.drop_column("transcript_error")
        batch_op.drop_column("transcript_status")

    with op.batch_alter_table("portal_kb_settings") as batch_op:
        batch_op.drop_column("media_transcription_enabled")

