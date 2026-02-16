docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, domain, install_type from portals where id=2;"
