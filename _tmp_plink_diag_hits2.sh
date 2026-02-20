cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
from sqlalchemy import select
from apps.backend.database import get_session_factory
from apps.backend.services.kb_rag import answer_from_kb, _extract_keywords, _keyword_hits
from apps.backend.models.kb import KBChunk

SessionLocal = get_session_factory()
portal_id = 2
q = 'как вызвать зомби дай подробную инструкцию'
qk = _extract_keywords(q)
print('QK', qk)
with SessionLocal() as db:
    answer, err, payload = answer_from_kb(db, portal_id=portal_id, query=q, audience='staff')
    srcs = (payload or {}).get('sources') or []
    for i,s in enumerate(srcs,1):
        cid=s.get('chunk_id')
        if not cid: continue
        ch=db.execute(select(KBChunk).where(KBChunk.id==cid)).scalar_one_or_none()
        if not ch: continue
        def hits(t):
            return _keyword_hits((t or ''), qk)
        this_h = hits(ch.text)
        prev=db.execute(select(KBChunk).where(KBChunk.file_id==ch.file_id, KBChunk.chunk_index==ch.chunk_index-1)).scalar_one_or_none()
        nextc=db.execute(select(KBChunk).where(KBChunk.file_id==ch.file_id, KBChunk.chunk_index==ch.chunk_index+1)).scalar_one_or_none()
        prev_h = hits(prev.text) if prev else -1
        next_h = hits(nextc.text) if nextc else -1
        print(f"{i}) idx={ch.chunk_index} hits(this/prev/next)={this_h}/{prev_h}/{next_h}")
PY