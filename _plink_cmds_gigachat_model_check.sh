cd /opt/teachbaseai
docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select value_json->>'embedding_model' as embedding_model, value_json->>'chat_model' as chat_model, value_json->>'model' as legacy_model from app_settings where key='gigachat';"
docker logs --since 2h teachbaseai-backend-1 | grep -i gigachat | tail -n 200
