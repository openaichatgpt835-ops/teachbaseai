SELECT created_at, trace_id, method, path, status_code, latency_ms
FROM bitrix_http_logs
WHERE direction='inbound'
  AND created_at > now() - interval '24 hours'
ORDER BY created_at DESC
LIMIT 200;
