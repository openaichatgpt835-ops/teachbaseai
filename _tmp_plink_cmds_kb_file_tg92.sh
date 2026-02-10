docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, portal_id, filename, status, created_at from kb_files where filename='tg_92.ogg' order by id desc limit 5;"
