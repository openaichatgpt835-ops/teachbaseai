set -e
TOKEN=$(curl -sS http://127.0.0.1:8080/v1/admin/auth/refresh | python - <<'PY'
import json,sys
j=json.load(sys.stdin)
print(j.get('access_token',''))
PY
)
redact() {
python - <<'PY'
import re,sys,json
s=sys.stdin.read()
# Mask JWT-like tokens
jwt_re=re.compile(r"([A-Za-z0-9_-]{6})[A-Za-z0-9_-]+([A-Za-z0-9_-]{4})")
# Mask JSON fields
def mask_fields(text):
    for key in ["access_token","refresh_token","AUTH_ID","REFRESH_ID","Authorization"]:
        text=re.sub(rf'("{key}"\s*:\s*")([^"]+)(")', lambda m: m.group(1)+m.group(2)[:6]+"..."+m.group(2)[-4:]+m.group(3), text)
    return text
s=mask_fields(s)
# Mask any JWT-like long strings
s=re.sub(r'([A-Za-z0-9_-]{10,})\.([A-Za-z0-9_-]{10,})\.([A-Za-z0-9_-]{10,})', lambda m: m.group(1)[:6]+"..."+m.group(3)[-4:], s)
print(s)
PY
}

call() {
  name=$1
  url=$2
  echo "=== ${name} ==="
  resp=$(curl -sS -w "\nSTATUS:%{http_code}\n" -H "Authorization: Bearer ${TOKEN}" -X POST "${url}")
  echo "$resp" | redact
}

call bot_check http://127.0.0.1:8080/v1/admin/portals/2/bot/check
call bot_fix_handlers http://127.0.0.1:8080/v1/admin/portals/2/bot/fix-handlers
call bot_ping http://127.0.0.1:8080/v1/admin/portals/2/bot/ping
