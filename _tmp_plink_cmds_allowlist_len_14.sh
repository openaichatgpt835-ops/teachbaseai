docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select user_id, telegram_username, length(telegram_username) from portal_users_access where portal_id=14;"
