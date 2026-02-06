cd /opt/teachbaseai
docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select key, value_json from app_settings where key='gigachat';"
