cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
from sqlalchemy import select
from apps.backend.database import get_session_factory
from apps.backend.services.kb_rag import answer_from_kb
from apps.backend.models.kb import KBChunk

SessionLocal = get_session_factory()
portal_id=2
q='??? ??????? ????? ??? ????????? ??????????'

with SessionLocal() as db:
    answer, err, payload = answer_from_kb(db, portal_id=portal_id, query=q, audience='staff')
    print('ERR:', err)
    print('ANSWER:\n', (answer or '')[:1400])
    srcs = (payload or {}).get('sources') or []
    print('\nSOURCES', len(srcs))
    for i,s in enumerate(srcs,1):
        fid=s.get('file_id'); cidx=s.get('chunk_index'); cid=s.get('chunk_id')
        print(str(i)+') file_id='+str(fid)+' chunk_id='+str(cid)+' chunk_index='+str(cidx)+' page='+str(s.get('page_num'))+' score='+str(s.get('score'))+' filename='+str(s.get('filename')))
        if cid:
            ch = db.execute(select(KBChunk).where(KBChunk.id==cid)).scalar_one_or_none()
            if ch:
                print('   chunk_text:', (ch.text or '')[:280].replace('\n',' '))
                prev = db.execute(select(KBChunk).where(KBChunk.file_id==ch.file_id, KBChunk.chunk_index==ch.chunk_index-1)).scalar_one_or_none()
                nxt = db.execute(select(KBChunk).where(KBChunk.file_id==ch.file_id, KBChunk.chunk_index==ch.chunk_index+1)).scalar_one_or_none()
                if prev: print('   prev:', (prev.text or '')[:160].replace('\n',' '))
                if nxt: print('   next:', (nxt.text or '')[:160].replace('\n',' '))
PY
