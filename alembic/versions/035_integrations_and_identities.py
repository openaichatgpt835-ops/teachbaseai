"""account integrations and user identities

Revision ID: 035_integrations_and_identities
Revises: 034_app_users_memberships
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "035_integrations_and_identities"
down_revision = "034_app_users_memberships"
branch_labels = None
depends_on = None


def _json_type(bind):
    return postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == "postgresql" else sa.JSON()


def upgrade() -> None:
    bind = op.get_bind()
    json_t = _json_type(bind)

    op.create_table(
        "account_integrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("external_key", sa.String(length=255), nullable=False),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("credentials_json", json_t, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("provider", "external_key", name="uq_account_integrations_provider_external_key"),
        sa.UniqueConstraint(
            "account_id",
            "provider",
            "external_key",
            name="uq_account_integrations_account_provider_external_key",
        ),
    )
    op.create_index("ix_account_integrations_account_id", "account_integrations", ["account_id"], unique=False)
    op.create_index("ix_account_integrations_provider", "account_integrations", ["provider"], unique=False)
    op.create_index("ix_account_integrations_portal_id", "account_integrations", ["portal_id"], unique=False)

    op.create_table(
        "app_user_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("integration_id", sa.Integer(), sa.ForeignKey("account_integrations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("display_value", sa.String(length=255), nullable=True),
        sa.Column("meta_json", json_t, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint(
            "provider",
            "integration_id",
            "external_id",
            name="uq_app_user_identities_provider_integration_external",
        ),
    )
    op.create_index("ix_app_user_identities_user_id", "app_user_identities", ["user_id"], unique=False)
    op.create_index("ix_app_user_identities_provider", "app_user_identities", ["provider"], unique=False)
    op.create_index("ix_app_user_identities_integration_id", "app_user_identities", ["integration_id"], unique=False)
    op.create_index("ix_app_user_identities_user_provider", "app_user_identities", ["user_id", "provider"], unique=False)

    op.alter_column("account_integrations", "status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_app_user_identities_user_provider", table_name="app_user_identities")
    op.drop_index("ix_app_user_identities_integration_id", table_name="app_user_identities")
    op.drop_index("ix_app_user_identities_provider", table_name="app_user_identities")
    op.drop_index("ix_app_user_identities_user_id", table_name="app_user_identities")
    op.drop_table("app_user_identities")

    op.drop_index("ix_account_integrations_portal_id", table_name="account_integrations")
    op.drop_index("ix_account_integrations_provider", table_name="account_integrations")
    op.drop_index("ix_account_integrations_account_id", table_name="account_integrations")
    op.drop_table("account_integrations")
