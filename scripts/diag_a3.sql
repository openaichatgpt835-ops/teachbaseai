SELECT created_at, trace_id, summary_json
FROM bitrix_http_logs
WHERE portal_id=(SELECT id FROM portals WHERE domain='b24-s57ni9.bitrix24.ru' LIMIT 1)
  AND kind='imbot_register'
ORDER BY created_at DESC
LIMIT 1;
