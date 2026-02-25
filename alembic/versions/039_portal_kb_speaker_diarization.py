"""portal kb speaker diarization toggle

Revision ID: 039_speaker_diarization
Revises: 038_media_transcription_option
Create Date: 2026-02-24
"""

from alembic import op
import sqlalchemy as sa


revision = "039_speaker_diarization"
down_revision = "038_media_transcription_option"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("portal_kb_settings") as batch_op:
        batch_op.add_column(sa.Column("speaker_diarization_enabled", sa.Boolean(), nullable=True))
    op.execute("UPDATE portal_kb_settings SET speaker_diarization_enabled = FALSE WHERE speaker_diarization_enabled IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("portal_kb_settings") as batch_op:
        batch_op.drop_column("speaker_diarization_enabled")
