"""account kb settings

Revision ID: 042_account_kb_settings
Revises: 041_account_billing
Create Date: 2026-03-27
"""

from alembic import op
import sqlalchemy as sa


revision = "042_account_kb_settings"
down_revision = "041_account_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_kb_settings",
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
        sa.Column("chat_model", sa.String(length=255), nullable=True),
        sa.Column("api_base", sa.String(length=255), nullable=True),
        sa.Column("prompt_preset", sa.String(length=32), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("top_p", sa.Float(), nullable=True),
        sa.Column("presence_penalty", sa.Float(), nullable=True),
        sa.Column("frequency_penalty", sa.Float(), nullable=True),
        sa.Column("allow_general", sa.Boolean(), nullable=True),
        sa.Column("strict_mode", sa.Boolean(), nullable=True),
        sa.Column("context_messages", sa.Integer(), nullable=True),
        sa.Column("context_chars", sa.Integer(), nullable=True),
        sa.Column("retrieval_top_k", sa.Integer(), nullable=True),
        sa.Column("retrieval_max_chars", sa.Integer(), nullable=True),
        sa.Column("lex_boost", sa.Float(), nullable=True),
        sa.Column("use_history", sa.Boolean(), nullable=True),
        sa.Column("use_cache", sa.Boolean(), nullable=True),
        sa.Column("system_prompt_extra", sa.Text(), nullable=True),
        sa.Column("show_sources", sa.Boolean(), nullable=True),
        sa.Column("sources_format", sa.String(length=16), nullable=True),
        sa.Column("media_transcription_enabled", sa.Boolean(), nullable=True),
        sa.Column("speaker_diarization_enabled", sa.Boolean(), nullable=True),
        sa.Column("collections_multi_assign", sa.Boolean(), nullable=True),
        sa.Column("smart_folder_threshold", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id"),
    )

    op.execute(
        """
        INSERT INTO account_kb_settings (
            account_id,
            embedding_model,
            chat_model,
            api_base,
            prompt_preset,
            temperature,
            max_tokens,
            top_p,
            presence_penalty,
            frequency_penalty,
            allow_general,
            strict_mode,
            context_messages,
            context_chars,
            retrieval_top_k,
            retrieval_max_chars,
            lex_boost,
            use_history,
            use_cache,
            system_prompt_extra,
            show_sources,
            sources_format,
            media_transcription_enabled,
            speaker_diarization_enabled,
            collections_multi_assign,
            smart_folder_threshold,
            updated_at
        )
        SELECT DISTINCT ON (p.account_id)
            p.account_id,
            s.embedding_model,
            s.chat_model,
            s.api_base,
            s.prompt_preset,
            s.temperature,
            s.max_tokens,
            s.top_p,
            s.presence_penalty,
            s.frequency_penalty,
            s.allow_general,
            s.strict_mode,
            s.context_messages,
            s.context_chars,
            s.retrieval_top_k,
            s.retrieval_max_chars,
            s.lex_boost,
            s.use_history,
            s.use_cache,
            s.system_prompt_extra,
            s.show_sources,
            s.sources_format,
            s.media_transcription_enabled,
            s.speaker_diarization_enabled,
            s.collections_multi_assign,
            s.smart_folder_threshold,
            s.updated_at
        FROM portal_kb_settings s
        JOIN portals p ON p.id = s.portal_id
        LEFT JOIN account_integrations ai
          ON ai.account_id = p.account_id
         AND ai.provider = 'bitrix'
         AND ai.portal_id = p.id
         AND (ai.status IS NULL OR ai.status <> 'deleted')
        WHERE p.account_id IS NOT NULL
        ORDER BY
            p.account_id,
            CASE
                WHEN COALESCE((ai.credentials_json ->> 'is_primary')::boolean, false) THEN 0
                ELSE 1
            END,
            p.id
        """
    )


def downgrade() -> None:
    op.drop_table("account_kb_settings")
