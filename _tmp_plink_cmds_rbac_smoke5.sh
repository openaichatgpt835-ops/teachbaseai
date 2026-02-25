cd /opt/teachbaseai
set -e
row=$(docker compose -f docker-compose.prod.yml exec -T postgres psql -U teachbaseai -d teachbaseai -At -F '|' -c "select ws.token, p.account_id from web_sessions ws join web_users wu on wu.id=ws.user_id join portals p on p.id=wu.portal_id where wu.email='lagutinaleks@gmail.com' order by ws.id desc limit 1;")
SESSION_TOKEN=$(echo "$row" | cut -d '|' -f1)
ACCOUNT_ID=$(echo "$row" | cut -d '|' -f2)
TS=$(date +%s)
INVITE_EMAIL="rbac_smoke_${TS}@example.com"
INVITE_LOGIN="rbac_smoke_${TS}"
CREATE_RESP=$(curl -sS -X POST "http://127.0.0.1:8080/api/v2/web/accounts/${ACCOUNT_ID}/invites/email" -H "Authorization: Bearer ${SESSION_TOKEN}" -H "Content-Type: application/json" -d "{\"email\":\"${INVITE_EMAIL}\",\"role\":\"member\",\"expires_days\":7}")
export CREATE_RESP
TOKEN=$(python3 -c 'import os,json,urllib.parse; o=json.loads(os.environ["CREATE_RESP"]); u=o.get("accept_url",""); q=urllib.parse.parse_qs(urllib.parse.urlparse(u).query); print((q.get("token") or [""])[0])')
ACCEPT_RESP=$(curl -sS -X POST "http://127.0.0.1:8080/api/v2/web/invites/${TOKEN}/accept" -H "Content-Type: application/json" -d "{\"login\":\"${INVITE_LOGIN}\",\"password\":\"SmokePass123\",\"display_name\":\"RBAC Smoke\"}")
USERS_RESP=$(curl -sS "http://127.0.0.1:8080/api/v2/web/accounts/${ACCOUNT_ID}/users" -H "Authorization: Bearer ${SESSION_TOKEN}")
INVITES_RESP=$(curl -sS "http://127.0.0.1:8080/api/v2/web/accounts/${ACCOUNT_ID}/invites" -H "Authorization: Bearer ${SESSION_TOKEN}")
export ACCEPT_RESP USERS_RESP INVITES_RESP INVITE_LOGIN
python3 - <<'PY'
import os, json
create=json.loads(os.environ['CREATE_RESP'])
accept=json.loads(os.environ['ACCEPT_RESP'])
users=json.loads(os.environ['USERS_RESP'])
invites=json.loads(os.environ['INVITES_RESP'])
login=os.environ['INVITE_LOGIN']
found=[i for i in users.get('items',[]) if ((i.get('web') or {}).get('login')==login)]
print('CREATE_STATUS', create.get('status'))
print('ACCEPT_STATUS', accept.get('status'))
print('FOUND', len(found))
print('LAST_INVITE_STATUS', (invites.get('items') or [{}])[0].get('status'))
assert create.get('status')=='ok'
assert accept.get('status')=='ok'
assert found
assert (invites.get('items') or [{}])[0].get('status')=='accepted'
PY
