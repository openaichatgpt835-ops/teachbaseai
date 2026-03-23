"""accounts slug and app sessions

Revision ID: 040_account_auth_v2
Revises: 039_speaker_diarization
Create Date: 2026-03-20
"""

from datetime import datetime
import re
import unicodedata

from alembic import op
import sqlalchemy as sa


revision = "040_account_auth_v2"
down_revision = "039_speaker_diarization"
branch_labels = None
depends_on = None


def _slugify_workspace(value: str | None, fallback: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return fallback
    normalized = unicodedata.normalize("NFKD", raw)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return slug or fallback


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.utcnow()

    op.add_column("accounts", sa.Column("slug", sa.String(length=128), nullable=True))
    op.create_index("ix_accounts_slug", "accounts", ["slug"], unique=True)

    op.create_table(
        "app_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("active_account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("token", sa.String(length=128), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_app_sessions_user_id", "app_sessions", ["user_id"], unique=False)
    op.create_index("ix_app_sessions_active_account_id", "app_sessions", ["active_account_id"], unique=False)
    op.create_index("ix_app_sessions_token", "app_sessions", ["token"], unique=True)

    accounts = sa.table(
        "accounts",
        sa.column("id", sa.Integer),
        sa.column("account_no", sa.BigInteger),
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
        sa.column("updated_at", sa.DateTime),
    )
    existing: set[str] = set()
    rows = bind.execute(
        sa.select(accounts.c.id, accounts.c.account_no, accounts.c.name, accounts.c.slug).order_by(accounts.c.id.asc())
    ).all()
    for row in rows:
        current = (row.slug or "").strip().lower()
        if current and current not in existing:
            existing.add(current)
            continue
        fallback = f"workspace-{int(row.account_no or row.id)}"
        base = _slugify_workspace(row.name, fallback)
        candidate = base
        suffix = 2
        while candidate in existing:
            candidate = f"{base}-{suffix}"
            suffix += 1
        bind.execute(
            accounts.update()
            .where(accounts.c.id == row.id)
            .values(slug=candidate, updated_at=now)
        )
        existing.add(candidate)


def downgrade() -> None:
    op.drop_index("ix_app_sessions_token", table_name="app_sessions")
    op.drop_index("ix_app_sessions_active_account_id", table_name="app_sessions")
    op.drop_index("ix_app_sessions_user_id", table_name="app_sessions")
    op.drop_table("app_sessions")

    op.drop_index("ix_accounts_slug", table_name="accounts")
    op.drop_column("accounts", "slug")
