cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
from sqlalchemy import select
from apps.backend.database import get_session_factory
from apps.backend.services.kb_rag import answer_from_kb
from apps.backend.models.kb import KBChunk, KBFile

SessionLocal = get_session_factory()
portal_id = 2
q = 'как вызвать зомби дай подробную инструкцию'

with SessionLocal() as db:
    answer, err, payload = answer_from_kb(db, portal_id=portal_id, query=q, audience='staff')
    print('ERR:', err)
    print('ANSWER:\n', (answer or '')[:2000])
    srcs = (payload or {}).get('sources') or []
    print('\nSOURCES:', len(srcs))
    for i, s in enumerate(srcs, 1):
        fid = s.get('file_id')
        cid = s.get('chunk_id')
        cidx = s.get('chunk_index')
        page = s.get('page_num')
        print(f"\n{i}) file_id={fid} chunk_id={cid} chunk_index={cidx} page={page} score={s.get('score')} filename={s.get('filename')}")
        ch = db.execute(select(KBChunk).where(KBChunk.id == cid)).scalar_one_or_none() if cid else None
        if not ch and fid is not None and cidx is not None:
            ch = db.execute(select(KBChunk).where(KBChunk.file_id==fid, KBChunk.chunk_index==cidx)).scalar_one_or_none()
        if ch:
            f = db.execute(select(KBFile).where(KBFile.id==ch.file_id)).scalar_one_or_none()
            print('   file:', (f.filename if f else 'n/a'))
            print('   this:', (ch.text or '').replace('\n',' ')[:500])
            prev = db.execute(select(KBChunk).where(KBChunk.file_id==ch.file_id, KBChunk.chunk_index==ch.chunk_index-1)).scalar_one_or_none()
            nxt = db.execute(select(KBChunk).where(KBChunk.file_id==ch.file_id, KBChunk.chunk_index==ch.chunk_index+1)).scalar_one_or_none()
            if prev:
                print('   prev:', (prev.text or '').replace('\n',' ')[:250])
            if nxt:
                print('   next:', (nxt.text or '').replace('\n',' ')[:250])
        else:
            print('   chunk not found in DB by id/index')

PY