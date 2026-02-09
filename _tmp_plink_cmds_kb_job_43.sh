docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, portal_id, status, error_message, payload_json from kb_jobs where id=43;"
