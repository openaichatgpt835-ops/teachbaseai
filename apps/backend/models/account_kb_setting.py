from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text

from apps.backend.database import Base


class AccountKBSetting(Base):
    __tablename__ = "account_kb_settings"

    account_id = Column(Integer, ForeignKey("accounts.id"), primary_key=True)
    embedding_model = Column(String(255), nullable=True)
    chat_model = Column(String(255), nullable=True)
    api_base = Column(String(255), nullable=True)
    prompt_preset = Column(String(32), nullable=True)
    temperature = Column(Float, nullable=True)
    max_tokens = Column(Integer, nullable=True)
    top_p = Column(Float, nullable=True)
    presence_penalty = Column(Float, nullable=True)
    frequency_penalty = Column(Float, nullable=True)
    allow_general = Column(Boolean, nullable=True)
    strict_mode = Column(Boolean, nullable=True)
    context_messages = Column(Integer, nullable=True)
    context_chars = Column(Integer, nullable=True)
    retrieval_top_k = Column(Integer, nullable=True)
    retrieval_max_chars = Column(Integer, nullable=True)
    lex_boost = Column(Float, nullable=True)
    use_history = Column(Boolean, nullable=True)
    use_cache = Column(Boolean, nullable=True)
    system_prompt_extra = Column(Text, nullable=True)
    show_sources = Column(Boolean, nullable=True)
    sources_format = Column(String(16), nullable=True)
    media_transcription_enabled = Column(Boolean, nullable=True)
    speaker_diarization_enabled = Column(Boolean, nullable=True)
    collections_multi_assign = Column(Boolean, nullable=True)
    smart_folder_threshold = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
