from datetime import datetime, date
from sqlalchemy import Column, Integer, Date, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB

from apps.backend.database import Base


class PortalTopicSummary(Base):
    __tablename__ = "portal_topic_summaries"

    id = Column(Integer, primary_key=True, index=True)
    portal_id = Column(Integer, ForeignKey("portals.id"), nullable=False, index=True)
    day = Column(Date, nullable=False, index=True)
    source_from = Column(DateTime, nullable=True)
    source_to = Column(DateTime, nullable=True)
    items = Column(JSONB, nullable=False, default=list)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
