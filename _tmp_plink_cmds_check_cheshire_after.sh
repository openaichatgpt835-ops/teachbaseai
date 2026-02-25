cd /opt/teachbaseai
set -e
docker compose -f docker-compose.prod.yml exec -T postgres psql -U teachbaseai -d teachbaseai -At -F '|' -c "select id,email,portal_id,email_verified_at from web_users where lower(email)='cheshirskithecat@mail.ru';"
