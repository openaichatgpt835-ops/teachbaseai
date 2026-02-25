cd /opt/teachbaseai
set -e
row=$(docker compose -f docker-compose.prod.yml exec -T postgres psql -U teachbaseai -d teachbaseai -At -F '|' -c "select ws.token, p.account_id from web_sessions ws join web_users wu on wu.id=ws.user_id join portals p on p.id=wu.portal_id where wu.email='lagutinaleks@gmail.com' order by ws.id desc limit 1;")
SESSION_TOKEN=$(echo "$row" | cut -d '|' -f1)
ACCOUNT_ID=$(echo "$row" | cut -d '|' -f2)
TS=$(date +%s)
INVITE_EMAIL="rbac_smoke_${TS}@example.com"
CREATE_RESP=$(curl -sS -X POST "http://127.0.0.1:8080/api/v2/web/accounts/${ACCOUNT_ID}/invites/email" \
  -H "Authorization: Bearer ${SESSION_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${INVITE_EMAIL}\",\"role\":\"member\",\"expires_days\":7}")
export CREATE_RESP
ACCEPT_URL=$(python3 -c 'import os,json; print(json.loads(os.environ["CREATE_RESP"]).get("accept_url",""))')
export ACCEPT_URL
TOKEN=$(python3 -c 'import os,urllib.parse; u=urllib.parse.urlparse(os.environ["ACCEPT_URL"]); print((urllib.parse.parse_qs(u.query).get("token") or [""])[0])' )
LOGIN="rbac_user_${TS}"
ACCEPT_RESP=$(curl -sS -X POST "http://127.0.0.1:8080/api/v2/web/invites/${TOKEN}/accept" \
  -H "Content-Type: application/json" \
  -d "{\"login\":\"${LOGIN}\",\"password\":\"SmokePass123\",\"display_name\":\"RBAC Smoke\"}")
USERS_RESP=$(curl -sS "http://127.0.0.1:8080/api/v2/web/accounts/${ACCOUNT_ID}/users" -H "Authorization: Bearer ${SESSION_TOKEN}")
LIST_RESP=$(curl -sS "http://127.0.0.1:8080/api/v2/web/accounts/${ACCOUNT_ID}/invites" -H "Authorization: Bearer ${SESSION_TOKEN}")
export USERS_RESP LIST_RESP ACCEPT_RESP LOGIN
MATCH=$(python3 -c 'import os,json; obj=json.loads(os.environ["USERS_RESP"]); login=os.environ["LOGIN"]; found=[{"user_id":i.get("user_id"),"role":i.get("role"),"kb_access":(i.get("permissions") or {}).get("kb_access")} for i in obj.get("items",[]) if ((i.get("web") or {}).get("login")==login)]; print(json.dumps(found, ensure_ascii=False))')
INVSTAT=$(python3 -c 'import os,json; obj=json.loads(os.environ["LIST_RESP"]); print(obj.get("items",[{}])[0].get("status",""))')

echo "ACCOUNT_ID=${ACCOUNT_ID}"
echo "CREATE_RESP=${CREATE_RESP}"
echo "ACCEPT_RESP=${ACCEPT_RESP}"
echo "USER_MATCH=${MATCH}"
echo "LAST_INVITE_STATUS=${INVSTAT}"
