docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, portal_id, job_type, status, payload_json, error_message, created_at from kb_jobs order by id desc limit 10;"
