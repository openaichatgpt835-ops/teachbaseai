"""Модели диалогов и сообщений."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship

from apps.backend.database import Base


class Dialog(Base):
    __tablename__ = "dialogs"

    id = Column(Integer, primary_key=True, index=True)
    portal_id = Column(Integer, ForeignKey("portals.id"), nullable=False, index=True)
    provider_dialog_id = Column(String(128), nullable=False, index=True)  # normalized
    provider_dialog_id_raw = Column(String(256))  # raw from provider
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("Message", back_populates="dialog")

    __table_args__ = (Index("ix_dialogs_portal_provider", "portal_id", "provider_dialog_id"),)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    dialog_id = Column(Integer, ForeignKey("dialogs.id"), nullable=False, index=True)
    provider_message_id = Column(String(128), index=True)
    direction = Column(String(8), nullable=False)  # rx, tx
    body = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    dialog = relationship("Dialog", back_populates="messages")
