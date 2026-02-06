cd /opt/teachbaseai
docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, portal_id, filename, status, error_message, updated_at from kb_files order by id desc limit 10;"
docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, portal_id, status, job_type, payload_json, updated_at from kb_jobs order by id desc limit 10;"
