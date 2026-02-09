docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select table_name from information_schema.tables where table_schema='public' and table_name like '%portal%';"
