docker exec -i teachbaseai-backend-1 curl -sS -X POST http://127.0.0.1:8000/v1/admin/auth/refresh | python - <<'PY'
import json,hashlib,sys
j=json.load(sys.stdin)
t=j.get('access_token','')
print('token_len', len(t))
print('token_sha256_12', hashlib.sha256(t.encode()).hexdigest()[:12])
PY
