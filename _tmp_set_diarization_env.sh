cd /opt/teachbaseai
python3 - <<'PY'
from pathlib import Path
p=Path('.env')
text=p.read_text(encoding='utf-8')
updates={
 'DIARIZATION_MIN_SPEAKERS':'2',
 'DIARIZATION_MAX_SPEAKERS':'6',
 'DIARIZATION_RETRY_MIN_SPEAKERS':'3',
 'DIARIZATION_RETRY_MIN_DURATION_SEC':'300',
}
for k,v in updates.items():
    if f"{k}=" in text:
        import re
        text=re.sub(rf'^{k}=.*$', f'{k}={v}', text, flags=re.M)
    else:
        text += f'\n{k}={v}\n'
p.write_text(text, encoding='utf-8')
print('env_updated')
PY
docker compose -f docker-compose.prod.yml up -d --no-deps worker-ingest