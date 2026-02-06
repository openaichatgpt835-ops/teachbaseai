"""Модель исходящих сообщений (outbox)."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index

from apps.backend.database import Base


class Outbox(Base):
    __tablename__ = "outbox"

    id = Column(Integer, primary_key=True, index=True)
    portal_id = Column(Integer, ForeignKey("portals.id"), nullable=False, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), index=True)
    status = Column(String(32), default="created")  # created, sent, error
    retry_count = Column(Integer, default=0)
    payload_json = Column(Text)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime)
