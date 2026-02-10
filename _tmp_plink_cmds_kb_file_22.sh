docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, filename, status from kb_files where id=22;"
