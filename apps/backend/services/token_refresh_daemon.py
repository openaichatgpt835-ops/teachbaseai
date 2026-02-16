from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from apps.backend.database import get_session_factory
from apps.backend.models.portal import PortalToken
from apps.backend.services.portal_tokens import ensure_fresh_access_token, BitrixAuthError

logger = logging.getLogger(__name__)


def refresh_tokens_once(skew_seconds: int = 1800) -> None:
    factory = get_session_factory()
    with factory() as db:
        now = datetime.utcnow()
        cutoff = now + timedelta(seconds=skew_seconds)
        rows = db.execute(select(PortalToken.portal_id, PortalToken.expires_at)).all()
        for portal_id, expires_at in rows:
            try:
                if not expires_at or expires_at <= cutoff:
                    ensure_fresh_access_token(
                        db,
                        int(portal_id),
                        now=now,
                        skew_seconds=skew_seconds,
                        trace_id="refresh_daemon",
                        force=False,
                    )
            except BitrixAuthError as e:
                logger.warning("refresh_daemon portal_id=%s error=%s", portal_id, e.code)
            except Exception as e:
                logger.warning("refresh_daemon portal_id=%s error=%s", portal_id, str(e)[:120])
