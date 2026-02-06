"""Кэш релевантных чанков для RAG по диалогу."""
from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Text, String, Index

from apps.backend.database import Base


class DialogRagCache(Base):
    __tablename__ = "dialog_rag_cache"

    id = Column(Integer, primary_key=True, index=True)
    dialog_id = Column(Integer, ForeignKey("dialogs.id"), nullable=False, index=True)
    portal_id = Column(Integer, ForeignKey("portals.id"), nullable=False, index=True)
    model = Column(String(128), nullable=False, index=True)
    chunk_ids_json = Column(Text, default="[]")
    keywords_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_dialog_rag_cache_dialog_model", "dialog_id", "model", unique=True),
    )
