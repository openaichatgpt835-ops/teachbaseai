cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
import json
from collections import Counter
p='/app/storage/kb/2/СКОЛЬКО ПОДНИМЕТ СПАРТАК.mp3.transcript.jsonl'
c=Counter(); n=0
with open(p, encoding='utf-8') as f:
  for ln in f:
    if not ln.strip():
      continue
    n+=1
    j=json.loads(ln)
    c[(j.get('speaker') or '').strip() or '<empty>'] += 1
print('rows', n)
print(dict(c))
PY