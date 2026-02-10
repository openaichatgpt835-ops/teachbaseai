docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, email, portal_id from web_users where email='lagutinaleks@gmail.com';"
