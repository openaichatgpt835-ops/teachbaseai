docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, portal_id, filename, status, error_message from kb_files order by id;"
