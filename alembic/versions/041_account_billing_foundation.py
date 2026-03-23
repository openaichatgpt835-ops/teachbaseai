"""account billing foundation

Revision ID: 041_account_billing
Revises: 040_account_auth_v2
Create Date: 2026-03-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "041_account_billing"
down_revision = "040_account_auth_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("billing_plans", sa.Column("code", sa.String(length=32), nullable=True))
    op.add_column("billing_plans", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("billing_plans", sa.Column("price_month", sa.Numeric(10, 2), nullable=True))
    op.add_column("billing_plans", sa.Column("currency", sa.String(length=16), nullable=True))
    op.add_column("billing_plans", sa.Column("limits_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("billing_plans", sa.Column("features_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("billing_plans", sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("now()")))
    op.add_column("billing_plans", sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.text("now()")))
    op.create_index("ix_billing_plans_code", "billing_plans", ["code"], unique=True)

    op.create_table(
        "account_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("billing_plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="trial"),
        sa.Column("trial_until", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_account_subscriptions_account_id", "account_subscriptions", ["account_id"])
    op.create_index("ix_account_subscriptions_plan_id", "account_subscriptions", ["plan_id"])

    op.create_table(
        "account_plan_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("limits_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("features_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("valid_from", sa.DateTime(), nullable=True),
        sa.Column("valid_to", sa.DateTime(), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_account_plan_overrides_account_id", "account_plan_overrides", ["account_id"])

    plans_table = sa.table(
        "billing_plans",
        sa.column("code", sa.String(length=32)),
        sa.column("name", sa.String(length=64)),
        sa.column("is_active", sa.Boolean()),
        sa.column("price_month", sa.Numeric(10, 2)),
        sa.column("currency", sa.String(length=16)),
        sa.column("limits_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("features_json", postgresql.JSONB(astext_type=sa.Text())),
    )
    op.bulk_insert(
        plans_table,
        [
            {
                "code": "start",
                "name": "Start",
                "is_active": True,
                "price_month": 4900.00,
                "currency": "RUB",
                "limits_json": {"requests_per_month": 3000, "media_minutes_per_month": 60, "max_users": 5, "max_storage_gb": 10},
                "features_json": {
                    "allow_model_selection": False,
                    "allow_advanced_model_tuning": False,
                    "allow_media_transcription": False,
                    "allow_speaker_diarization": False,
                    "allow_client_bot": True,
                    "allow_bitrix_integration": True,
                    "allow_amocrm_integration": False,
                    "allow_webhooks": False,
                },
            },
            {
                "code": "business",
                "name": "Business",
                "is_active": True,
                "price_month": 14900.00,
                "currency": "RUB",
                "limits_json": {"requests_per_month": 10000, "media_minutes_per_month": 300, "max_users": 25, "max_storage_gb": 50},
                "features_json": {
                    "allow_model_selection": True,
                    "allow_advanced_model_tuning": False,
                    "allow_media_transcription": True,
                    "allow_speaker_diarization": False,
                    "allow_client_bot": True,
                    "allow_bitrix_integration": True,
                    "allow_amocrm_integration": False,
                    "allow_webhooks": True,
                },
            },
            {
                "code": "pro",
                "name": "Pro",
                "is_active": True,
                "price_month": 39900.00,
                "currency": "RUB",
                "limits_json": {"requests_per_month": 50000, "media_minutes_per_month": 1200, "max_users": 200, "max_storage_gb": 500},
                "features_json": {
                    "allow_model_selection": True,
                    "allow_advanced_model_tuning": True,
                    "allow_media_transcription": True,
                    "allow_speaker_diarization": True,
                    "allow_client_bot": True,
                    "allow_bitrix_integration": True,
                    "allow_amocrm_integration": True,
                    "allow_webhooks": True,
                },
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_account_plan_overrides_account_id", table_name="account_plan_overrides")
    op.drop_table("account_plan_overrides")
    op.drop_index("ix_account_subscriptions_plan_id", table_name="account_subscriptions")
    op.drop_index("ix_account_subscriptions_account_id", table_name="account_subscriptions")
    op.drop_table("account_subscriptions")
    op.drop_index("ix_billing_plans_code", table_name="billing_plans")
    op.drop_column("billing_plans", "updated_at")
    op.drop_column("billing_plans", "created_at")
    op.drop_column("billing_plans", "features_json")
    op.drop_column("billing_plans", "limits_json")
    op.drop_column("billing_plans", "currency")
    op.drop_column("billing_plans", "price_month")
    op.drop_column("billing_plans", "is_active")
    op.drop_column("billing_plans", "code")
