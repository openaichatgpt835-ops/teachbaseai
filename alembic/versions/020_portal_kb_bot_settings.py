"""add portal kb bot settings

Revision ID: 020_portal_kb_bot_settings
Revises: 019_dialog_rag_cache
Create Date: 2026-02-06
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "020_portal_kb_bot_settings"
down_revision = "019_dialog_rag_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("portal_kb_settings", sa.Column("temperature", sa.Float(), nullable=True))
    op.add_column("portal_kb_settings", sa.Column("max_tokens", sa.Integer(), nullable=True))
    op.add_column("portal_kb_settings", sa.Column("top_p", sa.Float(), nullable=True))
    op.add_column("portal_kb_settings", sa.Column("presence_penalty", sa.Float(), nullable=True))
    op.add_column("portal_kb_settings", sa.Column("frequency_penalty", sa.Float(), nullable=True))
    op.add_column("portal_kb_settings", sa.Column("allow_general", sa.Boolean(), nullable=True))
    op.add_column("portal_kb_settings", sa.Column("strict_mode", sa.Boolean(), nullable=True))
    op.add_column("portal_kb_settings", sa.Column("context_messages", sa.Integer(), nullable=True))
    op.add_column("portal_kb_settings", sa.Column("context_chars", sa.Integer(), nullable=True))
    op.add_column("portal_kb_settings", sa.Column("retrieval_top_k", sa.Integer(), nullable=True))
    op.add_column("portal_kb_settings", sa.Column("retrieval_max_chars", sa.Integer(), nullable=True))
    op.add_column("portal_kb_settings", sa.Column("lex_boost", sa.Float(), nullable=True))
    op.add_column("portal_kb_settings", sa.Column("use_history", sa.Boolean(), nullable=True))
    op.add_column("portal_kb_settings", sa.Column("use_cache", sa.Boolean(), nullable=True))
    op.add_column("portal_kb_settings", sa.Column("system_prompt_extra", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("portal_kb_settings", "system_prompt_extra")
    op.drop_column("portal_kb_settings", "use_cache")
    op.drop_column("portal_kb_settings", "use_history")
    op.drop_column("portal_kb_settings", "lex_boost")
    op.drop_column("portal_kb_settings", "retrieval_max_chars")
    op.drop_column("portal_kb_settings", "retrieval_top_k")
    op.drop_column("portal_kb_settings", "context_chars")
    op.drop_column("portal_kb_settings", "context_messages")
    op.drop_column("portal_kb_settings", "strict_mode")
    op.drop_column("portal_kb_settings", "allow_general")
    op.drop_column("portal_kb_settings", "frequency_penalty")
    op.drop_column("portal_kb_settings", "presence_penalty")
    op.drop_column("portal_kb_settings", "top_p")
    op.drop_column("portal_kb_settings", "max_tokens")
    op.drop_column("portal_kb_settings", "temperature")
