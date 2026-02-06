docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select summary_json from bitrix_http_logs where trace_id='bed2f8a6-d346-4d';"
