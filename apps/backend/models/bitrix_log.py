"""Bitrix HTTP trace log."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text

from apps.backend.database import Base


class BitrixHttpLog(Base):
    __tablename__ = "bitrix_http_logs"

    id = Column(Integer, primary_key=True, index=True)
    trace_id = Column(String(64), index=True)
    portal_id = Column(Integer, ForeignKey("portals.id"), index=True)
    direction = Column(String(16), nullable=False)
    kind = Column(String(32), nullable=False)
    method = Column(String(16))
    path = Column(String(256))
    summary_json = Column(Text)
    status_code = Column(Integer)
    latency_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
