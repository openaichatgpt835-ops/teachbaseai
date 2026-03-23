cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
import json
from collections import Counter
p='/app/storage/kb/2/СКОЛЬКО ПОДНИМЕТ СПАРТАК.mp3.transcript.jsonl'
c=Counter(); rows=0
with open(p, encoding='utf-8') as f:
    for ln in f:
        ln=ln.strip()
        if not ln:
            continue
        rows += 1
        try:
            j=json.loads(ln)
        except Exception:
            continue
        c[(j.get('speaker') or '').strip() or '<empty>'] += 1
print('rows', rows)
print('speakers', dict(c))
PY