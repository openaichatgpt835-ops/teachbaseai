"""accounts core and portal account link

Revision ID: 033_accounts_core
Revises: 032_kb_pgvector
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa


revision = "033_accounts_core"
down_revision = "032_kb_pgvector"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_no", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_accounts_account_no", "accounts", ["account_no"], unique=True)
    op.create_index("ix_accounts_status", "accounts", ["status"], unique=False)

    op.add_column("portals", sa.Column("account_id", sa.Integer(), nullable=True))
    op.create_index("ix_portals_account_id", "portals", ["account_id"], unique=False)
    op.create_foreign_key(
        "fk_portals_account_id_accounts",
        "portals",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.alter_column("accounts", "status", server_default=None)


def downgrade() -> None:
    op.drop_constraint("fk_portals_account_id_accounts", "portals", type_="foreignkey")
    op.drop_index("ix_portals_account_id", table_name="portals")
    op.drop_column("portals", "account_id")

    op.drop_index("ix_accounts_status", table_name="accounts")
    op.drop_index("ix_accounts_account_no", table_name="accounts")
    op.drop_table("accounts")
