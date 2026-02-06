SELECT created_at, trace_id, method, path, status_code, summary_json
FROM bitrix_http_logs
WHERE path='/v1/bitrix/install/finalize'
ORDER BY created_at DESC
LIMIT 20;
