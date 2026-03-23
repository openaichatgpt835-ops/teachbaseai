cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
import json, time
from collections import Counter
from apps.backend.database import get_session_factory
from apps.backend.models.kb import KBFile
FILE_ID=74
for i in range(45):
    with get_session_factory()() as db:
        f=db.get(KBFile, FILE_ID)
        print('tick', i, 'status', f.status, 'transcript_status', f.transcript_status, 'err', (f.error_message or '')[:120])
        if (f.status or '').lower()=='ready' and (f.transcript_status or '').lower()=='ready':
            p=(f.storage_path or '') + '.transcript.jsonl'
            c=Counter(); rows=0
            with open(p, encoding='utf-8') as fh:
                for ln in fh:
                    ln=ln.strip()
                    if not ln: continue
                    rows += 1
                    try:
                        j=json.loads(ln)
                        c[(j.get('speaker') or '').strip() or '<empty>'] += 1
                    except Exception:
                        pass
            print('rows', rows)
            print('speakers', dict(c))
            break
    time.sleep(8)
PY