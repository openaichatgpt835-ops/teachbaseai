docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select portal_id, user_id from portal_users_access where portal_id=2;"
