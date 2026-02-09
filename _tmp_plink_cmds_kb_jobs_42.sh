docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, status, payload_json from kb_jobs where id in (41,42);"
