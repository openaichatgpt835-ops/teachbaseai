docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "update app_settings set value_json = jsonb_set(value_json, '{model}', '"'"'Embeddings'"'"', true) where key='gigachat';"
