docker exec teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, portal_id, filename, status, error_message, updated_at from kb_files where id=41;"
docker exec teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, status, error_message, payload_json, updated_at from kb_jobs where (payload_json->>'file_id')='41' order by id desc limit 5;"
