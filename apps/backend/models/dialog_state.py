"""Dialog state for bot flow execution."""
from datetime import datetime

from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB

from apps.backend.database import Base


class DialogState(Base):
    __tablename__ = "dialog_states"

    dialog_id = Column(Integer, ForeignKey("dialogs.id", ondelete="CASCADE"), primary_key=True)
    state_json = Column(JSONB, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
