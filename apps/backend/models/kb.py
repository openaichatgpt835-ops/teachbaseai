"""KB models: files, chunks, embeddings, sources, jobs."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from apps.backend.database import Base


class KBSource(Base):
    __tablename__ = "kb_sources"

    id = Column(Integer, primary_key=True, index=True)
    portal_id = Column(Integer, ForeignKey("portals.id"), nullable=False, index=True)
    source_type = Column(String(32), nullable=False)  # file|web|youtube|vk|rutube
    audience = Column(String(16), nullable=False, default="staff")  # staff|client
    url = Column(Text, nullable=True)
    title = Column(String(256), nullable=True)
    status = Column(String(32), nullable=False, default="new")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    files = relationship("KBFile", back_populates="source")
    chunks = relationship("KBChunk", back_populates="source")


class KBFile(Base):
    __tablename__ = "kb_files"

    id = Column(Integer, primary_key=True, index=True)
    portal_id = Column(Integer, ForeignKey("portals.id"), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("kb_sources.id"), nullable=True, index=True)
    filename = Column(String(256), nullable=False)
    audience = Column(String(16), nullable=False, default="staff")  # staff|client
    mime_type = Column(String(128), nullable=True)
    size_bytes = Column(Integer, nullable=False, default=0)
    storage_path = Column(Text, nullable=False)
    sha256 = Column(String(64), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="uploaded")  # uploaded|queued|processing|ready|error
    error_message = Column(Text, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    source = relationship("KBSource", back_populates="files")
    chunks = relationship("KBChunk", back_populates="file")

    __table_args__ = (
        Index("ix_kb_files_portal_status", "portal_id", "status"),
    )


class KBChunk(Base):
    __tablename__ = "kb_chunks"

    id = Column(Integer, primary_key=True, index=True)
    portal_id = Column(Integer, ForeignKey("portals.id"), nullable=False, index=True)
    file_id = Column(Integer, ForeignKey("kb_files.id"), nullable=True, index=True)
    source_id = Column(Integer, ForeignKey("kb_sources.id"), nullable=True, index=True)
    audience = Column(String(16), nullable=False, default="staff")  # staff|client
    chunk_index = Column(Integer, nullable=False, default=0)
    text = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=True)
    lang = Column(String(16), nullable=True)
    start_ms = Column(Integer, nullable=True)
    end_ms = Column(Integer, nullable=True)
    page_num = Column(Integer, nullable=True)
    sha256 = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    file = relationship("KBFile", back_populates="chunks")
    source = relationship("KBSource", back_populates="chunks")
    embeddings = relationship("KBEmbedding", back_populates="chunk")

    __table_args__ = (
        Index("ix_kb_chunks_portal_file_idx", "portal_id", "file_id", "chunk_index"),
    )


class KBEmbedding(Base):
    __tablename__ = "kb_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(Integer, ForeignKey("kb_chunks.id"), nullable=False, index=True)
    vector_json = Column(JSONB, nullable=True)
    vector_id = Column(String(128), nullable=True, index=True)
    model = Column(String(64), nullable=True)
    dim = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    chunk = relationship("KBChunk", back_populates="embeddings")


class KBJob(Base):
    __tablename__ = "kb_jobs"

    id = Column(Integer, primary_key=True, index=True)
    portal_id = Column(Integer, ForeignKey("portals.id"), nullable=False, index=True)
    job_type = Column(String(32), nullable=False)  # ingest|embed|reindex
    status = Column(String(32), nullable=False, default="queued")
    payload_json = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    trace_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_kb_jobs_portal_status", "portal_id", "status"),
    )
