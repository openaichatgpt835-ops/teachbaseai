SELECT created_at, trace_id, summary_json, status_code
FROM bitrix_http_logs
WHERE trace_id LIKE '6ce0f838%'
ORDER BY created_at ASC;
