"""revenue model v2 backfill

Revision ID: 054_revenue_model_v2_backfill
Revises: 053_revenue_model_v2_schema
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "054_revenue_model_v2_backfill"
down_revision = "053_revenue_model_v2_schema"
branch_labels = None
depends_on = None


plans_table = sa.table(
    "billing_plans",
    sa.column("id", sa.Integer()),
    sa.column("code", sa.String(length=32)),
    sa.column("name", sa.String(length=64)),
    sa.column("is_active", sa.Boolean()),
    sa.column("price_month", sa.Numeric(10, 2)),
    sa.column("currency", sa.String(length=16)),
    sa.column("limits_json", postgresql.JSONB(astext_type=sa.Text())),
    sa.column("features_json", postgresql.JSONB(astext_type=sa.Text())),
)

plan_versions_table = sa.table(
    "billing_plan_versions",
    sa.column("id", sa.Integer()),
    sa.column("plan_id", sa.Integer()),
    sa.column("version_code", sa.String(length=64)),
    sa.column("name", sa.String(length=128)),
    sa.column("price_month", sa.Numeric(12, 2)),
    sa.column("currency", sa.String(length=16)),
    sa.column("limits_json", postgresql.JSONB(astext_type=sa.Text())),
    sa.column("features_json", postgresql.JSONB(astext_type=sa.Text())),
    sa.column("is_active", sa.Boolean()),
    sa.column("is_default_for_new_accounts", sa.Boolean()),
)


def upgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    billing_plans = sa.Table("billing_plans", metadata, autoload_with=bind)
    billing_plan_versions = sa.Table("billing_plan_versions", metadata, autoload_with=bind)
    account_subscriptions = sa.Table("account_subscriptions", metadata, autoload_with=bind)

    plans = list(bind.execute(sa.select(billing_plans)).mappings())
    existing_versions = {
        row["version_code"]: row
        for row in bind.execute(sa.select(billing_plan_versions.c.version_code, billing_plan_versions.c.id)).mappings()
    }

    for plan in plans:
        code = (plan.get("code") or f"plan-{plan['id']}").strip().lower()
        version_code = f"{code}-initial"
        if version_code in existing_versions:
            continue
        bind.execute(
            sa.insert(plan_versions_table).values(
                plan_id=plan["id"],
                version_code=version_code,
                name=f"{plan.get('name') or code} · initial",
                price_month=plan.get("price_month") or 0,
                currency=(plan.get("currency") or "RUB"),
                limits_json=plan.get("limits_json") or {},
                features_json=plan.get("features_json") or {},
                is_active=bool(plan.get("is_active", True)),
                is_default_for_new_accounts=bool(plan.get("is_active", True)),
            )
        )

    plan_id_to_version_id = {
        int(row["plan_id"]): int(row["id"])
        for row in bind.execute(
            sa.select(billing_plan_versions.c.id, billing_plan_versions.c.plan_id, billing_plan_versions.c.version_code)
            .where(billing_plan_versions.c.version_code.like("%-initial"))
        ).mappings()
    }

    subscriptions = list(
        bind.execute(
            sa.select(account_subscriptions.c.id, account_subscriptions.c.plan_id, account_subscriptions.c.plan_version_id)
        ).mappings()
    )
    for row in subscriptions:
        if row.get("plan_version_id") is not None:
            continue
        plan_id = int(row["plan_id"])
        version_id = plan_id_to_version_id.get(plan_id)
        if version_id is None:
            raise RuntimeError(f"missing_initial_plan_version_for_plan:{plan_id}")
        bind.execute(
            sa.update(account_subscriptions)
            .where(account_subscriptions.c.id == row["id"])
            .values(plan_version_id=version_id)
        )


def downgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    billing_plan_versions = sa.Table("billing_plan_versions", metadata, autoload_with=bind)
    account_subscriptions = sa.Table("account_subscriptions", metadata, autoload_with=bind)

    initial_version_ids = [
        int(row["id"])
        for row in bind.execute(
            sa.select(billing_plan_versions.c.id).where(billing_plan_versions.c.version_code.like("%-initial"))
        ).mappings()
    ]

    if initial_version_ids:
        bind.execute(
            sa.update(account_subscriptions)
            .where(account_subscriptions.c.plan_version_id.in_(initial_version_ids))
            .values(plan_version_id=None)
        )
        bind.execute(sa.delete(billing_plan_versions).where(billing_plan_versions.c.id.in_(initial_version_ids)))
