cd /opt/teachbaseai
docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, status, job_type, payload_json, updated_at from kb_jobs where payload_json->>'file_id' = '1' order by id desc limit 5;"
