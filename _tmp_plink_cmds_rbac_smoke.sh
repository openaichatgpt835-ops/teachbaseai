cd /opt/teachbaseai
set -e
row=$(docker compose -f docker-compose.prod.yml exec -T postgres psql -U teachbaseai -d teachbaseai -At -F '|' -c "select ws.token, p.account_id from web_sessions ws join web_users wu on wu.id=ws.user_id join portals p on p.id=wu.portal_id where wu.email='lagutinaleks@gmail.com' order by ws.id desc limit 1;")
if [ -z "$row" ]; then
  echo "NO_SESSION_FOR_USER"
  exit 1
fi
SESSION_TOKEN=$(echo "$row" | cut -d '|' -f1)
ACCOUNT_ID=$(echo "$row" | cut -d '|' -f2)
echo "ACCOUNT_ID=$ACCOUNT_ID"

TS=$(date +%s)
INVITE_EMAIL="rbac_smoke_${TS}@example.com"
CREATE_RESP=$(curl -sS -X POST "http://127.0.0.1:8080/api/v2/web/accounts/${ACCOUNT_ID}/invites/email" \
  -H "Authorization: Bearer ${SESSION_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${INVITE_EMAIL}\",\"role\":\"member\",\"expires_days\":7}")

echo "CREATE_RESP=$CREATE_RESP"
ACCEPT_URL=$(python3 - <<'PY'
import json,sys
obj=json.loads(sys.stdin.read())
print(obj.get('accept_url',''))
PY
<<< "$CREATE_RESP")
if [ -z "$ACCEPT_URL" ]; then
  echo "NO_ACCEPT_URL"
  exit 1
fi
TOKEN=$(python3 - <<'PY'
import sys,urllib.parse
u=urllib.parse.urlparse(sys.stdin.read().strip())
print(urllib.parse.parse_qs(u.query).get('token',[''])[0])
PY
<<< "$ACCEPT_URL")
if [ -z "$TOKEN" ]; then
  echo "NO_TOKEN"
  exit 1
fi
LOGIN="rbac_user_${TS}"
ACCEPT_RESP=$(curl -sS -X POST "http://127.0.0.1:8080/api/v2/web/invites/${TOKEN}/accept" \
  -H "Content-Type: application/json" \
  -d "{\"login\":\"${LOGIN}\",\"password\":\"SmokePass123\",\"display_name\":\"RBAC Smoke\"}")

echo "ACCEPT_RESP=$ACCEPT_RESP"

LIST_RESP=$(curl -sS "http://127.0.0.1:8080/api/v2/web/accounts/${ACCOUNT_ID}/invites" \
  -H "Authorization: Bearer ${SESSION_TOKEN}")

echo "LIST_HEAD=$(python3 - <<'PY'
import json,sys
obj=json.loads(sys.stdin.read())
items=obj.get('items',[])
print(json.dumps(items[:2], ensure_ascii=False))
PY
<<< "$LIST_RESP")"

USERS_RESP=$(curl -sS "http://127.0.0.1:8080/api/v2/web/accounts/${ACCOUNT_ID}/users" \
  -H "Authorization: Bearer ${SESSION_TOKEN}")

echo "USER_MATCH=$(python3 - <<'PY'
import json,sys
obj=json.loads(sys.stdin.read())
found=[]
for it in obj.get('items',[]):
    web=it.get('web') or {}
    if (web.get('login') or '')=='"${LOGIN}"':
        found.append({'user_id':it.get('user_id'),'role':it.get('role'),'kb_access':(it.get('permissions') or {}).get('kb_access')})
print(json.dumps(found, ensure_ascii=False))
PY
<<< "$USERS_RESP")"
