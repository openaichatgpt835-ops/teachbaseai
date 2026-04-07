"""revenue model v2 schema

Revision ID: 053_revenue_model_v2_schema
Revises: 052_kb_access_levels_v2
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "053_revenue_model_v2_schema"
down_revision = "052_kb_access_levels_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_plan_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("billing_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("price_month", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default="RUB"),
        sa.Column("limits_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("features_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("valid_from", sa.DateTime(), nullable=True),
        sa.Column("valid_to", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_default_for_new_accounts", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_billing_plan_versions_plan_id", "billing_plan_versions", ["plan_id"])
    op.create_index("ix_billing_plan_versions_version_code", "billing_plan_versions", ["version_code"], unique=True)

    op.create_table(
        "billing_cohorts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("rule_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_billing_cohorts_code", "billing_cohorts", ["code"], unique=True)

    op.create_table(
        "billing_cohort_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cohort_id", sa.Integer(), sa.ForeignKey("billing_cohorts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_billing_cohort_assignments_account_id", "billing_cohort_assignments", ["account_id"])
    op.create_index("ix_billing_cohort_assignments_cohort_id", "billing_cohort_assignments", ["cohort_id"])

    op.create_table(
        "billing_cohort_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cohort_id", sa.Integer(), sa.ForeignKey("billing_cohorts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_version_id", sa.Integer(), sa.ForeignKey("billing_plan_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("discount_type", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("discount_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("feature_adjustments_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("limit_adjustments_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("valid_from", sa.DateTime(), nullable=True),
        sa.Column("valid_to", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_billing_cohort_policies_cohort_id", "billing_cohort_policies", ["cohort_id"])
    op.create_index("ix_billing_cohort_policies_plan_version_id", "billing_cohort_policies", ["plan_version_id"])

    op.create_table(
        "billing_account_adjustments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("target_key", sa.String(length=128), nullable=True),
        sa.Column("value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("valid_from", sa.DateTime(), nullable=True),
        sa.Column("valid_to", sa.DateTime(), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_billing_account_adjustments_account_id", "billing_account_adjustments", ["account_id"])
    op.create_index("ix_billing_account_adjustments_kind", "billing_account_adjustments", ["kind"])

    op.add_column("account_subscriptions", sa.Column("plan_version_id", sa.Integer(), nullable=True))
    op.add_column(
        "account_subscriptions",
        sa.Column("billing_cycle", sa.String(length=32), nullable=False, server_default="monthly"),
    )
    op.create_foreign_key(
        "fk_account_subscriptions_plan_version_id_billing_plan_versions",
        "account_subscriptions",
        "billing_plan_versions",
        ["plan_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_account_subscriptions_plan_version_id", "account_subscriptions", ["plan_version_id"])


def downgrade() -> None:
    op.drop_index("ix_account_subscriptions_plan_version_id", table_name="account_subscriptions")
    op.drop_constraint("fk_account_subscriptions_plan_version_id_billing_plan_versions", "account_subscriptions", type_="foreignkey")
    op.drop_column("account_subscriptions", "billing_cycle")
    op.drop_column("account_subscriptions", "plan_version_id")

    op.drop_index("ix_billing_account_adjustments_kind", table_name="billing_account_adjustments")
    op.drop_index("ix_billing_account_adjustments_account_id", table_name="billing_account_adjustments")
    op.drop_table("billing_account_adjustments")

    op.drop_index("ix_billing_cohort_policies_plan_version_id", table_name="billing_cohort_policies")
    op.drop_index("ix_billing_cohort_policies_cohort_id", table_name="billing_cohort_policies")
    op.drop_table("billing_cohort_policies")

    op.drop_index("ix_billing_cohort_assignments_cohort_id", table_name="billing_cohort_assignments")
    op.drop_index("ix_billing_cohort_assignments_account_id", table_name="billing_cohort_assignments")
    op.drop_table("billing_cohort_assignments")

    op.drop_index("ix_billing_cohorts_code", table_name="billing_cohorts")
    op.drop_table("billing_cohorts")

    op.drop_index("ix_billing_plan_versions_version_code", table_name="billing_plan_versions")
    op.drop_index("ix_billing_plan_versions_plan_id", table_name="billing_plan_versions")
    op.drop_table("billing_plan_versions")
