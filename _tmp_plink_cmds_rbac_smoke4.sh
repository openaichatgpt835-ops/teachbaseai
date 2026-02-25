cd /opt/teachbaseai
set -e
row=$(docker compose -f docker-compose.prod.yml exec -T postgres psql -U teachbaseai -d teachbaseai -At -F '|' -c "select ws.token, p.account_id from web_sessions ws join web_users wu on wu.id=ws.user_id join portals p on p.id=wu.portal_id where wu.email='lagutinaleks@gmail.com' order by ws.id desc limit 1;")
SESSION_TOKEN=$(echo "$row" | cut -d '|' -f1)
ACCOUNT_ID=$(echo "$row" | cut -d '|' -f2)
BASE_URL=http://127.0.0.1:8080 SESSION_TOKEN="$SESSION_TOKEN" ACCOUNT_ID="$ACCOUNT_ID" bash ./scripts/smoke_rbac_v2.sh
