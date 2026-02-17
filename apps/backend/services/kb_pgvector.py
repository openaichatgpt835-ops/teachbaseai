"""Optional pgvector helpers for KB embeddings.

This module is safe to import when pgvector is not installed/enabled.
All operations are guarded by config + postgres dialect checks.
"""

from __future__ import annotations

import json
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.backend.config import get_settings


def _is_pgvector_runtime_enabled(db: Session) -> bool:
    s = get_settings()
    if not bool(s.kb_pgvector_enabled):
        return False
    bind = db.get_bind()
    if bind is None:
        return False
    return bind.dialect.name == "postgresql"


def vector_to_literal(vec: Iterable[float] | None) -> str | None:
    if not vec:
        return None
    # pgvector textual input format: [1,2,3]
    return json.dumps([float(x) for x in vec], ensure_ascii=False, separators=(",", ":"))


def write_vector_column(db: Session, embedding_id: int, vec: Iterable[float]) -> None:
    if not _is_pgvector_runtime_enabled(db):
        return
    literal = vector_to_literal(vec)
    if not literal:
        return
    try:
        db.execute(
            text("UPDATE kb_embeddings SET vector_pg = CAST(:v AS vector) WHERE id = :id"),
            {"id": int(embedding_id), "v": literal},
        )
    except Exception:
        # Extension/column may be unavailable on current host; keep JSON path working.
        return


def query_top_chunks_by_pgvector(
    db: Session,
    *,
    portal_id: int,
    audience: str,
    model: str,
    query_vec: Iterable[float],
    limit: int,
) -> list[dict]:
    if not _is_pgvector_runtime_enabled(db):
        return []
    qvec = vector_to_literal(query_vec)
    if not qvec:
        return []
    sql = text(
        """
        SELECT
            c.text AS text,
            c.chunk_index AS chunk_index,
            c.start_ms AS start_ms,
            c.end_ms AS end_ms,
            c.page_num AS page_num,
            f.filename AS filename,
            f.mime_type AS mime_type,
            c.id AS chunk_id,
            f.id AS file_id,
            s.source_type AS source_type,
            s.url AS source_url,
            1 - (e.vector_pg <=> CAST(:qvec AS vector)) AS score
        FROM kb_embeddings e
        JOIN kb_chunks c ON c.id = e.chunk_id
        JOIN kb_files f ON f.id = c.file_id
        LEFT JOIN kb_sources s ON s.id = f.source_id
        WHERE
            c.portal_id = :portal_id
            AND f.status = 'ready'
            AND f.audience = :audience
            AND e.model = :model
            AND e.vector_pg IS NOT NULL
        ORDER BY e.vector_pg <=> CAST(:qvec AS vector)
        LIMIT :lim
        """
    )
    try:
        rows = db.execute(
            sql,
            {
                "qvec": qvec,
                "portal_id": int(portal_id),
                "audience": audience,
                "model": model,
                "lim": int(limit),
            },
        ).mappings().all()
    except Exception:
        return []
    return [dict(r) for r in rows]
