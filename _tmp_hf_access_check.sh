cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T worker-ingest python - <<'PY'
import os
from huggingface_hub import HfApi, hf_hub_download

token = (os.getenv('PYANNOTE_TOKEN') or os.getenv('HUGGINGFACE_TOKEN') or '').strip()
print('token_present', bool(token), 'token_prefix', token[:8] + '***' if token else '')
api = HfApi(token=token)
try:
    me = api.whoami()
    print('whoami_ok', me.get('name') or me.get('email') or 'ok')
except Exception as e:
    print('whoami_err', type(e).__name__, str(e)[:200])

for repo, filename in [
    ('pyannote/speaker-diarization-3.1', 'config.yaml'),
    ('pyannote/segmentation-3.0', 'pytorch_model.bin'),
]:
    try:
        p = hf_hub_download(repo_id=repo, filename=filename, token=token)
        print('download_ok', repo, filename, p)
    except Exception as e:
        print('download_err', repo, filename, type(e).__name__, str(e)[:220])
PY