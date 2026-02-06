SELECT path, status_code, count(*) as c
FROM bitrix_http_logs
WHERE direction='inbound'
  AND created_at > now() - interval '24 hours'
GROUP BY path, status_code
ORDER BY c DESC;
