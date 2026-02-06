docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, domain, created_at, updated_at from portals order by id;"
