cd /opt/teachbaseai
set -e
docker compose -f docker-compose.prod.yml exec -T postgres psql -U teachbaseai -d teachbaseai -At -F '|' -c "select id,email,portal_id,created_at from web_users where lower(email)='lagutinaleks@gmail.com' order by id;"
docker compose -f docker-compose.prod.yml exec -T postgres psql -U teachbaseai -d teachbaseai -At -F '|' -c "select ws.id,ws.user_id,wu.portal_id,ws.created_at from web_sessions ws join web_users wu on wu.id=ws.user_id where lower(wu.email)='lagutinaleks@gmail.com' order by ws.id desc limit 5;"
