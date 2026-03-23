cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
import json
p='/app/storage/kb/2/СКОЛЬКО ПОДНИМЕТ СПАРТАК.mp3.transcript.jsonl'
with open(p, encoding='utf-8') as f:
    for i,ln in enumerate(f):
        if i>=8: break
        j=json.loads(ln)
        print(i, j.get('start_ms'), j.get('end_ms'), j.get('speaker'))
PY