docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, domain, admin_user_id from portals where id=14;"
