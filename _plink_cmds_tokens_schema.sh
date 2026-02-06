docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "\dt"
docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "\d+ portals"
docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select table_name, column_name from information_schema.columns where table_schema='public' and (column_name ilike '%token%' or column_name ilike '%refresh%' or column_name ilike '%access%' or column_name ilike '%expires%') order by table_name, column_name;"
