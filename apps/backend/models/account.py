"""Account-centric RBAC v2 models."""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

from apps.backend.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    account_no = Column(BigInteger, unique=True, nullable=True, index=True)
    name = Column(String(255), nullable=True)
    slug = Column(String(128), unique=True, nullable=True, index=True)
    status = Column(String(32), nullable=False, default="active")
    owner_user_id = Column(Integer, ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AppUser(Base):
    __tablename__ = "app_users"

    id = Column(Integer, primary_key=True, index=True)
    display_name = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AppUserWebCredential(Base):
    __tablename__ = "app_user_web_credentials"

    user_id = Column(Integer, ForeignKey("app_users.id", ondelete="CASCADE"), primary_key=True)
    login = Column(String(255), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=True, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    email_verified_at = Column(DateTime, nullable=True)
    must_change_password = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AppSession(Base):
    __tablename__ = "app_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    active_account_id = Column(Integer, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    token = Column(String(128), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)


class AccountMembership(Base):
    __tablename__ = "account_memberships"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(32), nullable=False, default="member")
    status = Column(String(32), nullable=False, default="active")
    invited_by_user_id = Column(Integer, ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("account_id", "user_id", name="uq_account_memberships_account_user"),
    )


class AccountPermission(Base):
    __tablename__ = "account_permissions"

    membership_id = Column(Integer, ForeignKey("account_memberships.id", ondelete="CASCADE"), primary_key=True)
    kb_access = Column(String(16), nullable=False, default="none")
    can_invite_users = Column(Boolean, nullable=False, default=False)
    can_manage_settings = Column(Boolean, nullable=False, default=False)
    can_view_finance = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AccountIntegration(Base):
    __tablename__ = "account_integrations"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(32), nullable=False, index=True)  # bitrix|amo|telegram
    status = Column(String(32), nullable=False, default="active")
    external_key = Column(String(255), nullable=False)
    portal_id = Column(Integer, ForeignKey("portals.id", ondelete="SET NULL"), nullable=True, index=True)
    credentials_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "external_key", name="uq_account_integrations_provider_external_key"),
        UniqueConstraint("account_id", "provider", "external_key", name="uq_account_integrations_account_provider_external_key"),
    )


class AppUserIdentity(Base):
    __tablename__ = "app_user_identities"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(32), nullable=False, index=True)  # bitrix|telegram|amo
    integration_id = Column(Integer, ForeignKey("account_integrations.id", ondelete="CASCADE"), nullable=True, index=True)
    external_id = Column(String(255), nullable=False)
    display_value = Column(String(255), nullable=True)
    meta_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "integration_id", "external_id", name="uq_app_user_identities_provider_integration_external"),
        Index("ix_app_user_identities_user_provider", "user_id", "provider"),
    )


class AccountInvite(Base):
    __tablename__ = "account_invites"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=True, index=True)
    login = Column(String(255), nullable=True, index=True)
    role = Column(String(32), nullable=False, default="member")
    permissions_json = Column(JSONB, nullable=True)
    token = Column(String(128), nullable=False, unique=True, index=True)
    status = Column(String(32), nullable=False, default="pending")
    invited_by_user_id = Column(Integer, ForeignKey("app_users.id", ondelete="SET NULL"), nullable=False, index=True)
    accepted_user_id = Column(Integer, ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    accepted_at = Column(DateTime, nullable=True)


class AccountAuditLog(Base):
    __tablename__ = "account_audit_log"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    subject_type = Column(String(64), nullable=False, index=True)
    subject_id = Column(String(128), nullable=False, index=True)
    payload_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("ix_account_audit_log_account_created", "account_id", "created_at"),
    )
