"""billing payment attempts

Revision ID: 055_billing_payment_attempts
Revises: 054_revenue_model_v2_backfill
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "055_billing_payment_attempts"
down_revision = "054_revenue_model_v2_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_payment_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("account_subscriptions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("billing_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("plan_version_id", sa.Integer(), sa.ForeignKey("billing_plan_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="yookassa"),
        sa.Column("idempotence_key", sa.String(length=128), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default="RUB"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("confirmation_url", sa.Text(), nullable=True),
        sa.Column("return_url", sa.Text(), nullable=True),
        sa.Column("paid", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("test", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("provider_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("succeeded_at", sa.DateTime(), nullable=True),
        sa.Column("canceled_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_billing_payment_attempts_account_id", "billing_payment_attempts", ["account_id"])
    op.create_index("ix_billing_payment_attempts_subscription_id", "billing_payment_attempts", ["subscription_id"])
    op.create_index("ix_billing_payment_attempts_plan_id", "billing_payment_attempts", ["plan_id"])
    op.create_index("ix_billing_payment_attempts_plan_version_id", "billing_payment_attempts", ["plan_version_id"])
    op.create_index("ix_billing_payment_attempts_idempotence_key", "billing_payment_attempts", ["idempotence_key"], unique=True)
    op.create_index("ix_billing_payment_attempts_provider_payment_id", "billing_payment_attempts", ["provider_payment_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_billing_payment_attempts_provider_payment_id", table_name="billing_payment_attempts")
    op.drop_index("ix_billing_payment_attempts_idempotence_key", table_name="billing_payment_attempts")
    op.drop_index("ix_billing_payment_attempts_plan_version_id", table_name="billing_payment_attempts")
    op.drop_index("ix_billing_payment_attempts_plan_id", table_name="billing_payment_attempts")
    op.drop_index("ix_billing_payment_attempts_subscription_id", table_name="billing_payment_attempts")
    op.drop_index("ix_billing_payment_attempts_account_id", table_name="billing_payment_attempts")
    op.drop_table("billing_payment_attempts")
