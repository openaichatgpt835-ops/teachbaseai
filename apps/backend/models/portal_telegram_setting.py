"""Portal Telegram bot settings."""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text

from apps.backend.database import Base


class PortalTelegramSetting(Base):
    __tablename__ = "portal_telegram_settings"

    portal_id = Column(Integer, ForeignKey("portals.id", ondelete="CASCADE"), primary_key=True)
    staff_bot_token_enc = Column(Text, nullable=True)
    staff_bot_secret = Column(String(64), nullable=True)
    staff_bot_enabled = Column(Boolean, nullable=False, default=False)
    staff_allow_uploads = Column(Boolean, nullable=False, default=False)
    client_bot_token_enc = Column(Text, nullable=True)
    client_bot_secret = Column(String(64), nullable=True)
    client_bot_enabled = Column(Boolean, nullable=False, default=False)
    client_allow_uploads = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
