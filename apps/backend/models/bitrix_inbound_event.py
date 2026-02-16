"""Model for blackbox inbound events (POST /v1/bitrix/events)."""
from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from apps.backend.database import Base


class BitrixInboundEvent(Base):
    __tablename__ = "bitrix_inbound_events"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    trace_id = Column(String(64), index=True)
    portal_id = Column(Integer, ForeignKey("portals.id"), index=True)
    domain = Column(Text)
    member_id = Column(String(64), index=True)
    dialog_id = Column(String(128), index=True)
    user_id = Column(String(64), index=True)
    event_name = Column(String(128), index=True)
    remote_ip = Column(Text)
    method = Column(String(16), nullable=False)
    path = Column(String(256), nullable=False)
    query = Column(Text)
    content_type = Column(Text)
    headers_json = Column(JSONB)
    body_preview = Column(Text)
    body_truncated = Column(Boolean, nullable=False)
    body_sha256 = Column(String(64), nullable=False)
    parsed_redacted_json = Column(JSONB)
    hints_json = Column(JSONB)
    status_hint = Column(String(64))
