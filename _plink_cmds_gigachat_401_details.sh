cd /opt/teachbaseai
docker logs --since 2h teachbaseai-backend-1 | grep -i gigachat_token_request | tail -n 200
docker logs --since 2h teachbaseai-backend-1 | grep -i "/v1/admin/kb/models" | tail -n 50
docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select key, value_json->>'access_token_expires_at' as exp from app_settings where key='gigachat';"
