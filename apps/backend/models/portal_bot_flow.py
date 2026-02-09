"""Portal bot flow (client/staff)."""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB

from apps.backend.database import Base


class PortalBotFlow(Base):
    __tablename__ = "portal_bot_flows"

    portal_id = Column(Integer, ForeignKey("portals.id", ondelete="CASCADE"), primary_key=True)
    kind = Column(String(16), primary_key=True, default="client")  # client|staff
    draft_json = Column(JSONB, nullable=True)
    published_json = Column(JSONB, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
