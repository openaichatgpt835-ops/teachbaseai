cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
from sqlalchemy import select
from apps.backend.database import get_session_factory
from apps.backend.models.kb import KBFile, KBChunk

name = 'Erikson_Zdorovaya-zrelost-bez-trevogi-i-depressii-navyki-KPT-kotorye-pomogut-vam-myslit-gibko-i-poluchat-ot-zhizni-maksimum-v-lyubom-vozraste.793564.epub'
SessionLocal = get_session_factory()
with SessionLocal() as db:
    f = db.execute(select(KBFile).where(KBFile.filename==name)).scalar_one_or_none()
    print('file:', f.id if f else None, 'status:', f.status if f else None, 'portal:', f.portal_id if f else None)
    if not f:
        raise SystemExit(0)
    rows = db.execute(select(KBChunk).where(KBChunk.file_id==f.id).order_by(KBChunk.chunk_index)).scalars().all()
    print('chunks:', len(rows))
    for ch in rows[22:27]:
        print('idx', ch.chunk_index, 'id', ch.id, 'page', ch.page_num, 'len', len(ch.text or ''))
        print((ch.text or '').replace('\n',' ')[:320])
        print('---')
PY