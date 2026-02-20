cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
from sqlalchemy import select
from apps.backend.database import get_session_factory
from apps.backend.models.portal_kb_setting import PortalKBSetting

SessionLocal = get_session_factory()
with SessionLocal() as db:
    row = db.execute(select(PortalKBSetting).where(PortalKBSetting.portal_id==2)).scalar_one_or_none()
    print('FOUND', bool(row))
    if row:
        cols = [
            'portal_id','embed_model','chat_model','strict_mode','allow_general','retrieval_top_k',
            'retrieval_max_chars','retrieval_min_score','retrieval_min_keyword_hits',
            'show_sources','sources_format','rag_v2_enabled','style_pass_enabled'
        ]
        for c in cols:
            print(c, getattr(row,c,None))
PY