cd /opt/teachbaseai
docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, portal_id, filename, status, error_message, updated_at from kb_files where filename like 'ЛИИС%' order by id desc limit 3;"
docker logs --since 30m teachbaseai-worker-1 | grep -i ocr | tail -n 200
