"""merge heads 021_portal_telegram_uploads and 026_activity_events_web_email

Revision ID: 027_merge_heads
Revises: 021_portal_telegram_uploads, 026_activity_events_web_email
Create Date: 2026-02-09
"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "027_merge_heads"
down_revision: Union[str, Sequence[str], None] = (
    "021_portal_telegram_uploads",
    "026_activity_events_web_email",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
