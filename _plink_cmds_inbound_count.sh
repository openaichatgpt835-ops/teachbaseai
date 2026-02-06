docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select count(*) as inbound_last_hour from bitrix_inbound_events where created_at > now() - interval '1 hour';"
