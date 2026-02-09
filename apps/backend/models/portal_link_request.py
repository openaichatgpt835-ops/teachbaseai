"""Portal link requests between Bitrix portal and web account."""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text

from apps.backend.database import Base


class PortalLinkRequest(Base):
    __tablename__ = "portal_link_requests"

    id = Column(Integer, primary_key=True, index=True)
    portal_id = Column(Integer, ForeignKey("portals.id", ondelete="CASCADE"), nullable=False, index=True)
    web_user_id = Column(Integer, ForeignKey("web_users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_portal_id = Column(Integer, ForeignKey("portals.id"), nullable=True, index=True)
    status = Column(String(16), nullable=False, default="pending")  # pending|approved|rejected
    merge_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
