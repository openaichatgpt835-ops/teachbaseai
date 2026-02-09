"""Модели порталов и токенов."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from apps.backend.database import Base


class Portal(Base):
    __tablename__ = "portals"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(255), unique=True, nullable=False, index=True)
    member_id = Column(String(64), index=True)
    application_token = Column(String(128), index=True)
    status = Column(String(32), default="pending")  # pending, active, error, suspended
    install_type = Column(String(16), default="unknown")  # local | market | unknown
    local_client_id = Column(String(128), index=True)  # local.* для Local App, per-portal
    local_client_secret_encrypted = Column(Text)  # ����������, �� � env
    admin_user_id = Column(Integer, nullable=True, index=True)  # Bitrix portal admin (installer)
    metadata_json = Column(Text)
    welcome_message = Column(Text, nullable=False, default="Привет! Я Teachbase AI. Напишите «ping» — отвечу «pong».")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tokens = relationship("PortalToken", back_populates="portal")
    users_access = relationship("PortalUsersAccess", back_populates="portal")


class PortalToken(Base):
    __tablename__ = "portal_tokens"

    id = Column(Integer, primary_key=True, index=True)
    portal_id = Column(Integer, ForeignKey("portals.id"), nullable=False, index=True)
    access_token = Column(Text)
    refresh_token = Column(Text)
    expires_at = Column(DateTime)
    scope = Column(String(512))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    portal = relationship("Portal", back_populates="tokens")


class PortalUsersAccess(Base):
    __tablename__ = "portal_users_access"

    id = Column(Integer, primary_key=True, index=True)
    portal_id = Column(Integer, ForeignKey("portals.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)  # Bitrix user_id
    display_name = Column(String(128), nullable=True)
    telegram_username = Column(String(64), nullable=True, index=True)
    kind = Column(String(16), nullable=False, default="bitrix")  # bitrix|web|amo
    created_by_bitrix_user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_welcome_at = Column(DateTime, nullable=True)
    last_welcome_hash = Column(String(64), nullable=True)  # sha256 of welcome text for idempotency

    portal = relationship("Portal", back_populates="users_access")

    __table_args__ = (
        UniqueConstraint("portal_id", "user_id", name="uq_portal_users_access_portal_user"),
        UniqueConstraint("portal_id", "telegram_username", name="uq_portal_users_access_telegram_username"),
    )

