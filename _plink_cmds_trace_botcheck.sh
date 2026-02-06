docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select kind, status_code, summary_json from bitrix_http_logs where trace_id='971485c4-826a-40' order by created_at;"
