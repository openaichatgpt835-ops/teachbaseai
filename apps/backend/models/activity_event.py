"""Activity events for web/iframe/AI usage analytics."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index

from apps.backend.database import Base


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id = Column(Integer, primary_key=True, index=True)
    portal_id = Column(Integer, ForeignKey("portals.id"), nullable=True, index=True)
    web_user_id = Column(Integer, ForeignKey("web_users.id"), nullable=True, index=True)
    kind = Column(String(32), nullable=False, index=True)  # web|iframe|ai
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_activity_events_kind_time", "kind", "created_at"),
    )
