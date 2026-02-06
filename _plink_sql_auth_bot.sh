cd /opt/teachbaseai
docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, (parsed_redacted_json->'auth')::text as auth, (parsed_redacted_json->'data'->'BOT')::text as bot from bitrix_inbound_events where id=28;"
