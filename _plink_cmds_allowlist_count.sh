docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select portal_id, count(*) as allowed_users from portal_users_access where portal_id=2 group by portal_id;"
