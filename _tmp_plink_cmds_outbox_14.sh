docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, status, payload_json from outbox where portal_id=14 order by id desc limit 5;"
