cd /opt/teachbaseai
set -e
docker compose -f docker-compose.prod.yml exec -T postgres psql -U teachbaseai -d teachbaseai -At -F '|' -c "select id,email,portal_id,email_verified_at,created_at from web_users where lower(email)='cheshirskithecat@mail.ru';"
docker compose -f docker-compose.prod.yml exec -T postgres psql -U teachbaseai -d teachbaseai -At -F '|' -c "select c.user_id,c.login,c.email,c.email_verified_at,au.status from app_user_web_credentials c join app_users au on au.id=c.user_id where lower(c.email)='cheshirskithecat@mail.ru' or lower(c.login)='cheshirskithecat@mail.ru';"
