"""Модель событий."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index

from apps.backend.database import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    portal_id = Column(Integer, ForeignKey("portals.id"), nullable=False, index=True)
    provider_event_id = Column(String(128), index=True)
    event_type = Column(String(64))  # rx, send_ok, send_err
    payload_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_events_portal_provider", "portal_id", "provider_event_id"),)
